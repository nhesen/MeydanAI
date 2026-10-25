from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import AppConfig
from app.core.device import resolve_device
from app.core.types import BBox, Detection, Role


def class_role(name: str, config: AppConfig) -> Role:
    label = name.strip().lower()
    if label in {item.lower() for item in config.detection.ball_classes}:
        return Role.BALL
    if label in {item.lower() for item in config.detection.referee_classes}:
        return Role.REFEREE
    if label in {item.lower() for item in config.detection.keeper_classes}:
        return Role.GOALKEEPER
    if label in {item.lower() for item in config.detection.player_classes}:
        return Role.PLAYER if label != "goalkeeper" else Role.GOALKEEPER
    if label == "person":
        return Role.PLAYER
    return Role.UNKNOWN


class FootballDetector:
    """Ultralytics YOLO wrapper. Tests inject detections without loading weights."""

    def __init__(self, config: AppConfig, model: Any | None = None) -> None:
        self.config = config
        self.device = resolve_device(config.detection.device)
        self._model = model
        self._ball_detector = None
        self.ball_model_skipped = ""
        self._names = self._class_names(getattr(model, "names", {}))

    def _resolved_ball_model(self) -> str:
        raw = (self.config.detection.ball_model or "").strip()
        if not raw:
            return ""
        path = Path(raw)
        if path.is_file() or path.parent == Path("."):
            return raw
        # A configured specialist that is not on disk must not abort player detection.
        self.ball_model_skipped = raw
        return ""

    @staticmethod
    def _class_names(names: Any) -> dict[int, str]:
        items = names.items() if isinstance(names, dict) else enumerate(names or [])
        return {int(key): str(value) for key, value in items}

    @property
    def model(self) -> Any:
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.config.detection.model)
            self._names = self._class_names(self._model.names)
        return self._model

    def detect(self, frame: np.ndarray) -> list[Detection]:
        return self.detect_many([frame])[0]

    def detect_many(self, frames: list[np.ndarray]) -> list[list[Detection]]:
        detected = self._detect_many_raw(frames)
        ball_model = self._resolved_ball_model()
        if ball_model:
            if self._ball_detector is None:
                ball_config = replace(self.config, detection=replace(self.config.detection,
                    model=ball_model, ball_model="",
                    image_size=self.config.detection.ball_image_size))
                self._ball_detector = FootballDetector(ball_config)
            balls = self._ball_detector.detect_many(frames)
            return [[item for item in people if item.role is not Role.BALL] +
                    [item for item in found if item.role is Role.BALL]
                    for people, found in zip(detected, balls, strict=True)]
        if not self.config.detection.ball_tiles:
            return detected
        # Rescue small balls lost when a wide broadcast frame is reduced to 640px.
        # Sequential overlapping tiles bound GPU memory; players remain full-frame.
        for frame, detections in zip(frames, detected, strict=True):
            if any(item.role is Role.BALL and item.confidence >= .35 for item in detections):
                continue
            h, w = frame.shape[:2]
            if max(h, w) <= self.config.detection.image_size:
                continue
            tile_w, tile_h = int(w * .6), int(h * .6)
            candidates = []
            for y in (0, h - tile_h):
                for x in (0, w - tile_w):
                    for item in self._detect_many_raw([frame[y:y+tile_h, x:x+tile_w]])[0]:
                        if item.role is Role.BALL:
                            box = item.bbox
                            item.bbox = BBox(box.x1+x, box.y1+y, box.x2+x, box.y2+y)
                            candidates.append(item)
            for item in sorted(candidates, key=lambda d: d.confidence, reverse=True):
                if not any(other.role is Role.BALL and other.bbox.iou(item.bbox) > .3 for other in detections):
                    detections.append(item)
        return detected

    def _detect_many_raw(self, frames: list[np.ndarray]) -> list[list[Detection]]:
        if not frames:
            return []
        try:
            results = list(
                self.model.predict(
                    frames,
                    verbose=False,
                    conf=min(
                        self.config.detection.confidence,
                        self.config.detection.ball_confidence,
                    ),
                    imgsz=self.config.detection.image_size,
                    device=self.device,
                    half=self.device not in {"cpu", "none"},
                )
            )
        except RuntimeError as exc:
            # A batch that fits on one GPU may exceed another GPU's memory.
            # Retry smaller batches without hiding unrelated inference errors.
            if len(frames) <= 1 or "out of memory" not in str(exc).lower():
                raise
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            midpoint = len(frames) // 2
            return self._detect_many_raw(frames[:midpoint]) + self._detect_many_raw(
                frames[midpoint:]
            )
        if len(results) != len(frames):
            raise RuntimeError(
                f"YOLO returned {len(results)} results for {len(frames)} video frames."
            )
        return [self.parse_result(result) for result in results]

    def parse_result(self, result: Any) -> list[Detection]:
        names = self._class_names(getattr(result, "names", None) or self._names)
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        detections: list[Detection] = []
        xyxy = (
            boxes.xyxy.cpu().numpy()
            if hasattr(boxes.xyxy, "cpu")
            else np.asarray(boxes.xyxy)
        )
        confs = (
            boxes.conf.cpu().numpy()
            if hasattr(boxes.conf, "cpu")
            else np.asarray(boxes.conf)
        )
        clss = (
            boxes.cls.cpu().numpy()
            if hasattr(boxes.cls, "cpu")
            else np.asarray(boxes.cls)
        )
        ids = None
        if getattr(boxes, "id", None) is not None:
            raw_ids = (
                boxes.id.cpu().numpy()
                if hasattr(boxes.id, "cpu")
                else np.asarray(boxes.id)
            )
            ids = [int(value) for value in raw_ids]
        for index, (box, conf, cls_id) in enumerate(
            zip(xyxy, confs, clss, strict=False)
        ):
            if (
                not np.isfinite(box).all()
                or not np.isfinite(conf)
                or not np.isfinite(cls_id)
            ):
                continue
            if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
                continue
            name = str(names.get(int(cls_id), int(cls_id)))
            role = class_role(name, self.config)
            if role is Role.UNKNOWN:
                continue
            min_conf = (
                self.config.detection.ball_confidence
                if role is Role.BALL
                else self.config.detection.confidence
            )
            if float(conf) < min_conf:
                continue
            detections.append(
                Detection(
                    bbox=BBox(
                        float(box[0]), float(box[1]), float(box[2]), float(box[3])
                    ),
                    confidence=float(conf),
                    role=role,
                    track_id=None if ids is None else ids[index],
                    class_name=name,
                )
            )
        return detections

    def iter_tracks(
        self, source: str | np.ndarray
    ) -> Iterable[tuple[np.ndarray, list[Detection]]]:
        tracker = (
            "botsort.yaml"
            if self.config.tracking.tracker.lower() == "botsort"
            else "bytetrack.yaml"
        )
        stream = self.model.track(
            source=source,
            persist=True,
            tracker=tracker,
            verbose=False,
            conf=min(
                self.config.detection.confidence, self.config.detection.ball_confidence
            ),
            imgsz=self.config.detection.image_size,
            device=self.device,
            stream=True,
        )
        for result in stream:
            frame = result.orig_img
            yield frame, self.parse_result(result)

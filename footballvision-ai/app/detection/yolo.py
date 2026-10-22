from __future__ import annotations

from collections.abc import Iterable
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
        self._names: dict[int, str] = {}

    @property
    def model(self) -> Any:
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.config.detection.model)
            self._names = {int(k): str(v) for k, v in self._model.names.items()}
        return self._model

    def detect(self, frame: np.ndarray) -> list[Detection]:
        result = next(
            iter(
                self.model.predict(
                    frame,
                    verbose=False,
                    conf=min(self.config.detection.confidence, self.config.detection.ball_confidence),
                    imgsz=self.config.detection.image_size,
                    device=self.device,
                )
            )
        )
        return self.parse_result(result)

    def parse_result(self, result: Any) -> list[Detection]:
        names = getattr(result, "names", None) or self._names
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []
        detections: list[Detection] = []
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.asarray(boxes.xyxy)
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.asarray(boxes.conf)
        clss = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.asarray(boxes.cls)
        ids = None
        if getattr(boxes, "id", None) is not None:
            raw_ids = boxes.id.cpu().numpy() if hasattr(boxes.id, "cpu") else np.asarray(boxes.id)
            ids = [int(value) for value in raw_ids]
        for index, (box, conf, cls_id) in enumerate(zip(xyxy, confs, clss, strict=False)):
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
                    bbox=BBox(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
                    confidence=float(conf),
                    role=role,
                    track_id=None if ids is None else ids[index],
                    class_name=name,
                )
            )
        return detections

    def iter_tracks(self, source: str | np.ndarray) -> Iterable[tuple[np.ndarray, list[Detection]]]:
        tracker = (
            "botsort.yaml" if self.config.tracking.tracker.lower() == "botsort" else "bytetrack.yaml"
        )
        stream = self.model.track(
            source=source,
            persist=True,
            tracker=tracker,
            verbose=False,
            conf=min(self.config.detection.confidence, self.config.detection.ball_confidence),
            imgsz=self.config.detection.image_size,
            device=self.device,
            stream=True,
        )
        for result in stream:
            frame = result.orig_img
            yield frame, self.parse_result(result)

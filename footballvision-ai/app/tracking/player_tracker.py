from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import AppConfig
from app.core.types import Detection, Role


@dataclass
class _ActiveTrack:
    track_id: int
    detection: Detection
    misses: int = 0
    hits: int = 1
    history: list[Detection] = field(default_factory=list)


class PlayerTracker:
    """ByteTrack-compatible wrapper with an IoU fallback for tests and CPU labs."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._next_id = 1
        self._active: dict[int, _ActiveTrack] = {}
        self._supervision = None

    def update(self, detections: list[Detection], frame_shape: tuple[int, int] | None = None) -> list[Detection]:
        people = [item for item in detections if item.role is not Role.BALL]
        balls = [item for item in detections if item.role is Role.BALL]
        tracked = self._update_players(people, frame_shape)
        return tracked + balls

    def _update_players(
        self, detections: list[Detection], frame_shape: tuple[int, int] | None
    ) -> list[Detection]:
        if self._try_supervision(detections, frame_shape):
            return detections
        return self._iou_update(detections)

    def _try_supervision(
        self, detections: list[Detection], frame_shape: tuple[int, int] | None
    ) -> bool:
        if any(item.track_id is not None for item in detections):
            return True
        if frame_shape is None:
            return False
        try:
            import numpy as np
            import supervision as sv
        except Exception:
            return False
        if self._supervision is None:
            self._supervision = sv.ByteTrack(
                lost_track_buffer=self.config.tracking.lost_track_buffer,
                minimum_matching_threshold=self.config.tracking.match_threshold,
                frame_rate=25,
            )
        if not detections:
            self._supervision.update_with_detections(sv.Detections.empty())
            return True
        xyxy = np.array([item.bbox.as_xyxy() for item in detections], dtype=np.float32)
        conf = np.array([item.confidence for item in detections], dtype=np.float32)
        wrapped = sv.Detections(xyxy=xyxy, confidence=conf)
        tracked = self._supervision.update_with_detections(wrapped)
        if tracked.tracker_id is None:
            return True
        for detection, track_id in zip(detections, tracked.tracker_id, strict=False):
            detection.track_id = int(track_id)
        return True

    def _iou_update(self, detections: list[Detection]) -> list[Detection]:
        unused = set(range(len(detections)))
        assignments: dict[int, int] = {}
        for track in sorted(self._active.values(), key=lambda item: item.hits, reverse=True):
            best_index = None
            best_iou = self.config.tracking.min_iou
            for index in unused:
                iou = track.detection.bbox.iou(detections[index].bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_index = index
            if best_index is None:
                track.misses += 1
                continue
            unused.remove(best_index)
            assignments[best_index] = track.track_id
            track.detection = detections[best_index]
            track.misses = 0
            track.hits += 1
        for index in unused:
            track_id = self._next_id
            self._next_id += 1
            assignments[index] = track_id
            self._active[track_id] = _ActiveTrack(track_id=track_id, detection=detections[index])
        alive = {
            track_id: track
            for track_id, track in self._active.items()
            if track.misses <= self.config.tracking.lost_track_buffer
        }
        self._active = alive
        labelled: list[Detection] = []
        for index, detection in enumerate(detections):
            detection.track_id = assignments.get(index)
            labelled.append(detection)
        return labelled

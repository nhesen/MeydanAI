from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.types import Detection, PlayerTrack, Role


class PlayerEvidence:
    """Keep at most three useful, separated full-resolution player crops per ID."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.candidates: dict[int, list[dict[str, Any]]] = {}

    def observe(self, frame: np.ndarray, detection: Detection, index: int, time_s: float) -> None:
        if detection.track_id is None or detection.role not in {Role.PLAYER, Role.GOALKEEPER}:
            return
        height, width = frame.shape[:2]
        box = detection.bbox
        x1, x2 = max(0, int(box.x1)-3), min(width, int(box.x2)+3)
        y1, y2 = max(0, int(box.y1)-3), min(height, int(box.y2)+3)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 24 or crop.shape[1] < 10:
            return
        sharpness = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        score = crop.shape[0] * crop.shape[1] * detection.confidence * np.log1p(sharpness)
        candidates = self.candidates.setdefault(detection.track_id, [])
        near = next((item for item in candidates if abs(item["timestamp_ms"]-time_s*1000) < 500), None)
        replacing = near or (min(candidates, key=lambda item: item["score"]) if len(candidates) >= 3 else None)
        if replacing is not None and score <= replacing["score"] * 1.05:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"player_{detection.track_id}_{index}.jpg"
        success, encoded = cv2.imencode(".jpg", crop)
        if not success:
            return
        path.write_bytes(encoded.tobytes())
        if replacing is not None:
            candidates.remove(replacing)
        candidates.append({"path": str(path), "timestamp_ms": round(time_s*1000),
                           "width": crop.shape[1], "height": crop.shape[0],
                           "score": float(score)})

    def for_track(self, track: PlayerTrack) -> dict[str, Any]:
        candidates = [item for identity in [track.track_id, *track.merged_from]
                      for item in self.candidates.get(identity, [])]
        selected: list[dict[str, Any]] = []
        for item in sorted(candidates, key=lambda item: item["score"], reverse=True):
            if all(abs(item["timestamp_ms"]-other["timestamp_ms"]) >= 500 for other in selected):
                selected.append(item)
            if len(selected) >= 3:
                break
        return {"image_path": selected[0]["path"] if selected else None,
                "evidence_images": [{key: value for key, value in item.items() if key != "score"}
                                    for item in selected]}

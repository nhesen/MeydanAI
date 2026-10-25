"""Conservative jersey-number suggestions, never a confirmed player identity."""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JerseyObservation:
    number: int
    confidence: float
    timestamp_ms: int


def jersey_consensus(observations: list[JerseyObservation]) -> dict[str, Any]:
    """Require matching high-score readings in separate video frames."""
    votes: dict[int, list[JerseyObservation]] = defaultdict(list)
    frame_numbers: dict[int, set[int]] = defaultdict(set)
    for item in observations:
        if (
            not 0 <= item.number <= 99
            or not math.isfinite(item.confidence)
            or not 0.93 <= item.confidence <= 1
            or item.timestamp_ms < 0
        ):
            continue
        frame_numbers[item.timestamp_ms].add(item.number)
    for item in sorted(observations, key=lambda row: row.timestamp_ms):
        if frame_numbers.get(item.timestamp_ms) != {item.number}:
            continue
        if not math.isfinite(item.confidence) or not 0.93 <= item.confidence <= 1:
            continue
        previous = votes[item.number]
        if not previous or item.timestamp_ms - previous[-1].timestamp_ms >= 500:
            previous.append(item)
    if not votes:
        return {}
    number, agreeing = max(votes.items(), key=lambda row: len(row[1]))
    total = sum(len(items) for items in votes.values())
    if len(agreeing) < 2 or len(agreeing) / max(total, 1) < 2 / 3:
        return {}
    return {
        "jersey_candidate": number,
        "jersey_confidence": round(min(item.confidence for item in agreeing), 4),
        "ocr_observations": len(agreeing),
    }


class JerseyReader:
    def __init__(self, *, enabled: bool = True, engine: Any | None = None) -> None:
        self.enabled = enabled
        self._engine = engine
        self._unavailable = False

    def read(self, images: list[tuple[Path, int]]) -> dict[str, Any]:
        if not self.enabled or self._unavailable:
            return {}
        observations: list[JerseyObservation] = []
        for path, timestamp in images[:3]:
            # OpenCV's Windows filename reader cannot open every Unicode path.
            try:
                encoded = np.frombuffer(path.read_bytes(), dtype=np.uint8)
                crop = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
            except (OSError, cv2.error):
                continue
            if crop is None or crop.shape[0] < 80 or crop.shape[1] < 24:
                continue
            height, width = crop.shape[:2]
            # Exclude the face, shorts and pitch markings around the feet.
            torso = crop[
                int(height * 0.15) : int(height * 0.65), int(width * 0.08) : int(width * 0.92)
            ]
            scale = min(4.0, 640 / max(torso.shape[:2]))
            torso = cv2.resize(torso, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            try:
                if self._engine is None:
                    from rapidocr import RapidOCR

                    self._engine = RapidOCR(
                        params={
                            "Global.log_level": "error",
                            "Global.text_score": 0.93,
                            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                        }
                    )
                result = self._engine(torso, use_cls=False)
                texts = getattr(result, "txts", None) or []
                scores = getattr(result, "scores", None)
                scores = [] if scores is None else scores
                for text, score in zip(texts, scores, strict=False):
                    value = str(text).strip()
                    if re.fullmatch(r"[0-9]{1,2}", value):
                        observations.append(JerseyObservation(int(value), float(score), timestamp))
            except Exception:
                logger.warning("jersey_ocr_unavailable", exc_info=True)
                self._unavailable = True
                break
        return jersey_consensus(observations)

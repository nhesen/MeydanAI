"""Football-specific observations; unknown is a valid result, never forced into a team.

Inspired by the capabilities demonstrated by MatchLens; independently implemented.
See MATCHLENS-REVIEW.md for source references and differences.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import cv2
import numpy as np

Array = np.ndarray[Any, Any]
TEAM_COLORS = {1: (255, 175, 65), 2: (110, 105, 255), None: (185, 185, 185)}
COLOUR_WEIGHTS = np.array([0.25, 1.3, 1.3], dtype=np.float32)


def detection_classes(names: dict[int, str]) -> tuple[list[int], list[int]]:
    people, _referees, balls = role_classes(names)
    if not people:
        raise ValueError("Model must have person, player or goalkeeper labels.")
    return people, balls


def role_classes(names: dict[int, str]) -> tuple[list[int], list[int], list[int]]:
    """Players/keepers for metrics, referees separately, then ball classes."""
    labels = {index: name.lower() for index, name in names.items()}
    players = [index for index, name in labels.items() if name in {"player", "goalkeeper"}]
    if not players:
        players = [index for index, name in labels.items() if name == "person"]
    referees = [index for index, name in labels.items() if name == "referee"]
    balls = [index for index, name in labels.items() if name in {"sports ball", "ball", "football"}]
    return players, referees, balls


def field_region(frame: Array) -> Array | None:
    """Conservative grass-region heuristic; fall back to unfiltered if no pitch is found."""
    height, width = frame.shape[:2]
    small = cv2.resize(frame, (width // 4, height // 4))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (28, 35, 25), (95, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < mask.size * 0.12:
        return None
    return np.asarray(cv2.convexHull(largest), dtype=np.float32) * 4


def on_field(box: list[float], region: Array | None) -> bool:
    if region is None:
        return True
    x1, _y1, x2, y2 = box
    return bool(cv2.pointPolygonTest(region, ((x1 + x2) / 2, y2), True) >= -4)


def order_pitch_quad(points: Array) -> Array:
    """Perimeter order: near-left, near-right, far-right, far-left."""
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    by_y = pts[np.argsort(pts[:, 1])]
    near = by_y[2:][np.argsort(by_y[2:, 0])]
    far = by_y[:2][np.argsort(by_y[:2, 0])]
    return np.stack([near[0], near[1], far[1], far[0]])


def visible_pitch_points(frame: Array) -> list[tuple[float, float]] | None:
    """Four corners of the visible grass surface, normalized to image size."""
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (28, 35, 25), (95, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < mask.size * 0.12:
        return None
    box = cv2.boxPoints(cv2.minAreaRect(largest))
    box[:, 0] = np.clip(box[:, 0], 0, width - 1)
    box[:, 1] = np.clip(box[:, 1], 0, height - 1)
    ordered = order_pitch_quad(box)
    polygon = ordered.astype(np.float32)
    if not cv2.isContourConvex(polygon) or cv2.contourArea(polygon) < 0.05 * width * height:
        return None
    return [(float(x / width), float(y / height)) for x, y in ordered]


def adjust_visible_length(calibration: Any) -> Any:
    """Full-pitch length on a cropped tactical view inflates speed past the quality filter."""
    if len(calibration.points) != 4 or calibration.length_m < 90:
        return calibration
    xs = [point[0] for point in calibration.points]
    ys = [point[1] for point in calibration.points]
    if max(xs) - min(xs) > 0.7 and max(ys) - min(ys) < 0.72:
        return calibration.model_copy(update={"length_m": 60.0})
    return calibration


def shirt_feature(frame: Array, box: list[float]) -> Array | None:
    """Sample central torso in Lab, retaining white, black and green jerseys."""
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    if bw < 4 or bh < 8:
        return None
    if bh < 18:
        left, right = max(0, int(x1 + 0.18 * bw)), min(width, int(x1 + 0.82 * bw))
        top, bottom = max(0, int(y1 + 0.08 * bh)), min(height, int(y1 + 0.58 * bh))
    else:
        left, right = max(0, int(x1 + 0.25 * bw)), min(width, int(x1 + 0.75 * bw))
        top, bottom = max(0, int(y1 + 0.18 * bh)), min(height, int(y1 + 0.48 * bh))
    crop = frame[top:bottom, left:right]
    if crop.size < 24:
        return None
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    return np.asarray(np.median(lab, axis=0), dtype=np.float32)


class JerseyGroups:
    """Two visual jersey groups, not verified clubs or player identities."""

    def __init__(self) -> None:
        self.features: dict[int, list[Array]] = defaultdict(list)
        self.votes: dict[int, Counter[int]] = defaultdict(Counter)
        self.centers: Array | None = None

    def observe(self, identity: int, feature: Array | None) -> None:
        if feature is None:
            return
        if len(self.features[identity]) < 12:
            self.features[identity].append(feature)
        if self.centers is None:
            return
        distances = np.linalg.norm((self.centers - feature) * COLOUR_WEIGHTS, axis=1)
        winner = int(np.argmin(distances))
        # Reject third kits/referees and ambiguous appearances instead of forcing a label.
        if (
            float(distances[winner]) <= 48
            and abs(float(distances[0] - distances[1])) >= 15
            and abs(float(self.centers[winner, 0] - feature[0])) < 80
        ):
            self.votes[identity][winner + 1] += 1

    def fit(self) -> bool:
        candidates = [
            np.median(values, axis=0) for values in self.features.values() if len(values) >= 2
        ]
        if len(candidates) < 4:
            return False
        data = np.asarray(candidates, dtype=np.float32)
        # Multiple deterministic starts; penalize small groups and discard gross outliers.
        best: tuple[float, Array] | None = None
        for first in range(len(data)):
            second = int(np.argmax(np.linalg.norm((data - data[first]) * COLOUR_WEIGHTS, axis=1)))
            centers = data[[first, second]].copy()
            for _ in range(15):
                distances = np.linalg.norm(
                    (data[:, None, :] - centers[None, :, :]) * COLOUR_WEIGHTS, axis=2
                )
                labels = distances.argmin(axis=1)
                groups = [data[labels == group] for group in range(2)]
                if any(len(group) < 2 for group in groups):
                    break
                updated = np.array([np.median(group, axis=0) for group in groups])
                if np.allclose(updated, centers):
                    centers = updated
                    break
                centers = updated
            distances = np.linalg.norm(
                (data[:, None, :] - centers[None, :, :]) * COLOUR_WEIGHTS, axis=2
            )
            labels = distances.argmin(axis=1)
            if (
                min(np.bincount(labels, minlength=2)) < 2
                or np.linalg.norm((centers[0] - centers[1]) * COLOUR_WEIGHTS) < 30
            ):
                continue
            score = float(np.minimum(distances.min(axis=1), 60).sum())
            if best is None or score < best[0]:
                best = score, centers
        if best is None:
            return False
        # Stable group numbering by brightness; numbering never implies home/away.
        self.centers = best[1][np.argsort(best[1][:, 0])]
        for identity, values in self.features.items():
            for feature in list(values):
                self.observe(identity, feature)
        return True

    def team(self, identity: int) -> int | None:
        votes = self.votes[identity]
        if not votes:
            return None
        winner, count = votes.most_common(1)[0]
        return winner if count >= 2 and count / votes.total() >= 0.6 else None

    def summary(self) -> dict[str, Any]:
        return {
            "method": "central-torso Lab colour with temporal votes",
            "ready": self.centers is not None,
            "groups_are_verified_teams": False,
            "centers_lab": self.centers.round(2).tolist() if self.centers is not None else [],
        }


def heatmap(tracks: list[dict[str, Any]], length: float | None, width: float | None) -> Array:
    """Observation density; no reconstruction of hidden runs."""
    counts = np.zeros((360, 640), dtype=np.float32)
    for track in tracks:
        for sample in track["samples"]:
            if length and width:
                point = sample["ground"]
                if point is None:
                    continue
                x, y = point[0] / length, point[1] / width
            else:
                x, y = sample["x"], sample["y"]
            if 0 <= x <= 1 and 0 <= y <= 1:
                counts[min(359, int(y * 360)), min(639, int(x * 640))] += 1
    density = cv2.GaussianBlur(counts, (0, 0), 12)
    scaled = (density / max(float(density.max()), 1e-9) * 255).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    if length and width:
        cv2.rectangle(colored, (2, 2), (637, 357), (240, 240, 240), 1)
        cv2.line(colored, (320, 2), (320, 357), (240, 240, 240), 1)
        cv2.circle(colored, (320, 180), 40, (240, 240, 240), 1)
    return np.asarray(colored)

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from app.core.types import BBox, Role, TeamId

Array = np.ndarray


def torso_hist(frame: Array, bbox: BBox, bins: int = 12) -> list[float] | None:
    height, width = frame.shape[:2]
    bw, bh = bbox.width, bbox.height
    if bw < 6 or bh < 10:
        return None
    left = max(0, int(bbox.x1 + 0.22 * bw))
    right = min(width, int(bbox.x1 + 0.78 * bw))
    top = max(0, int(bbox.y1 + 0.16 * bh))
    bottom = min(height, int(bbox.y1 + 0.52 * bh))
    crop = frame[top:bottom, left:right]
    if crop.size < 24:
        return None
    import cv2

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [bins, bins], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    return [float(value) for value in hist]


def lab_median(frame: Array, bbox: BBox) -> Array | None:
    height, width = frame.shape[:2]
    bw, bh = bbox.width, bbox.height
    if bw < 4 or bh < 8:
        return None
    left = max(0, int(bbox.x1 + 0.25 * bw))
    right = min(width, int(bbox.x1 + 0.75 * bw))
    top = max(0, int(bbox.y1 + 0.18 * bh))
    bottom = min(height, int(bbox.y1 + 0.48 * bh))
    crop = frame[top:bottom, left:right]
    if crop.size < 24:
        return None
    import cv2

    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    feature = np.median(lab, axis=0).astype(np.float32)
    # Shirt chroma is more stable than brightness across sun and shadow.
    feature[0] *= 0.2
    return feature


class TeamAssigner:
    """Two-team Lab clustering with temporal votes. Keepers/referees stay unclustered."""

    def __init__(self) -> None:
        self.features: dict[int, list[Array]] = defaultdict(list)
        self.votes: dict[int, Counter[int]] = defaultdict(Counter)
        self.centers: Array | None = None
        self.roles: dict[int, Role] = {}

    def observe(self, track_id: int, feature: Array | None, role: Role) -> None:
        self.roles[track_id] = role
        if feature is None or role in {Role.REFEREE, Role.BALL}:
            return
        if len(self.features[track_id]) < 16:
            self.features[track_id].append(feature)
        if self.centers is None:
            return
        distances = np.linalg.norm(self.centers - feature, axis=1)
        winner = int(np.argmin(distances))
        if (
            float(distances[winner]) <= 55
            and abs(float(distances[0] - distances[1])) >= 10
        ):
            self.votes[track_id][winner] += 1

    def fit(self) -> bool:
        samples = [
            np.median(values, axis=0)
            for track_id, values in self.features.items()
            if len(values) >= 2 and self.roles.get(track_id) is Role.PLAYER
        ]
        if len(samples) < 4:
            return False
        data = np.asarray(samples, dtype=np.float32)
        best: tuple[float, Array] | None = None
        for first in range(len(data)):
            second = int(np.argmax(np.linalg.norm(data - data[first], axis=1)))
            centers = data[[first, second]].copy()
            for _ in range(12):
                labels = np.linalg.norm(
                    data[:, None, :] - centers[None, :, :], axis=2
                ).argmin(axis=1)
                groups = [data[labels == index] for index in range(2)]
                if any(len(group) < 2 for group in groups):
                    break
                updated = np.array(
                    [np.median(group, axis=0) for group in groups], dtype=np.float32
                )
                if np.allclose(updated, centers):
                    centers = updated
                    break
                centers = updated
            distances = np.linalg.norm(data[:, None, :] - centers[None, :, :], axis=2)
            labels = distances.argmin(axis=1)
            if min(np.bincount(labels, minlength=2)) < 2:
                continue
            if np.linalg.norm(centers[0] - centers[1]) < 18:
                continue
            score = float(np.minimum(distances.min(axis=1), 70).sum())
            if best is None or score < best[0]:
                best = score, centers
        if best is None:
            return False
        updated = best[1]
        if self.centers is None:
            updated = updated[np.argsort(updated[:, 0])]
        elif np.linalg.norm(updated - self.centers) > np.linalg.norm(
            updated[::-1] - self.centers
        ):
            updated = updated[::-1]
        self.centers = updated
        self.votes.clear()
        for track_id, values in self.features.items():
            for feature in values:
                self.observe(track_id, feature, self.roles.get(track_id, Role.PLAYER))
        return True

    def team(self, track_id: int) -> TeamId:
        if self.roles.get(track_id) is Role.REFEREE:
            return TeamId.UNKNOWN
        votes = self.votes[track_id]
        if not votes:
            return TeamId.UNKNOWN
        winner, count = votes.most_common(1)[0]
        if count < 2 or count / votes.total() < 0.55:
            return TeamId.UNKNOWN
        return TeamId.HOME if winner == 0 else TeamId.AWAY

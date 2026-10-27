"""Goal mouths in the image, for cameras where the pitch quad is not the goal line.

The metre homography maps a grass outline. On a wide hali-saha camera that
outline is the picture, and the ball in the net never crosses x < 0. A goal
here is the ball inside the visible goal frame.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class GoalMouth:
    name: str
    polygon: np.ndarray


def _near_posts(frame: np.ndarray) -> tuple[int, int] | None:
    """Two goal posts on the right edge. Players elsewhere do not pass this."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    vertical = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    if float(vertical[220:430, 1180:1270].mean()) < 55.0:
        return None
    column = vertical[210:430, 1160:1280].mean(axis=0)
    peaks: list[tuple[float, int]] = []
    for index in range(2, len(column) - 2):
        strength = float(column[index])
        if strength < 40 or strength < float(column[index - 1]) or strength < float(column[index + 1]):
            continue
        peaks.append((strength, 1160 + index))
    peaks.sort(reverse=True)
    for _, left in peaks:
        for _, right in peaks:
            if 28 <= right - left <= 80:
                return left, right
    return None


def _horizontal_edge(frame: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> int | None:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    horizontal = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    band = horizontal[y0:y1, x0:x1]
    if band.size == 0:
        return None
    row = band.mean(axis=1)
    index = int(np.argmax(row))
    if float(row[index]) < 20:
        return None
    return y0 + index


def near_goal_mouth(frame: np.ndarray) -> GoalMouth | None:
    posts = _near_posts(frame)
    if posts is None:
        return None
    left, right = posts
    top = _horizontal_edge(frame, left, right, 200, 320) or 250
    bottom = _horizontal_edge(frame, left, right, 360, 450) or 400
    if bottom - top < 70:
        return None
    polygon = np.array(
        [[left, top], [right, top - 8], [right + 4, bottom], [left - 4, bottom - 6]],
        dtype=np.float32,
    )
    return GoalMouth("near", polygon)


# The far camera in this hali-saha does not move. The red posts stay in this
# window; a red shirt elsewhere must not become the goal.
_FAR_MOUTH = np.array([[255, 250], [400, 248], [405, 358], [250, 360]], dtype=np.float32)


def far_goal_mouth(frame: np.ndarray) -> GoalMouth | None:
    """Small red goal on the far camera. The near-goal camera must not match."""
    if _near_posts(frame) is not None:
        return None
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 70, 50), (12, 255, 220)),
        cv2.inRange(hsv, (168, 70, 50), (180, 255, 220)),
    )
    window = np.zeros(red.shape, dtype=np.uint8)
    cv2.fillConvexPoly(window, _FAR_MOUTH.astype(np.int32), 255)
    if int(cv2.countNonZero(cv2.bitwise_and(red, window))) < 40:
        return None
    return GoalMouth("far", _FAR_MOUTH.copy())


def goal_mouth(frame: np.ndarray) -> GoalMouth | None:
    return near_goal_mouth(frame) or far_goal_mouth(frame)


def ball_in_mouth(pixel: tuple[float, float] | None, mouth: GoalMouth | None) -> bool:
    if pixel is None or mouth is None:
        return False
    return cv2.pointPolygonTest(mouth.polygon, (float(pixel[0]), float(pixel[1])), False) >= 0


def cluster_goal_times(times: list[float], gap_s: float = 2.0) -> list[tuple[float, float]]:
    """Group repeated sightings of one goal. A replay after a cut stays separate."""
    if not times:
        return []
    ordered = sorted(times)
    groups: list[list[float]] = [[ordered[0]]]
    for time_s in ordered[1:]:
        if time_s - groups[-1][-1] <= gap_s:
            groups[-1].append(time_s)
        else:
            groups.append([time_s])
    return [(group[0], group[-1]) for group in groups if group[-1] - group[0] >= 0.12 or len(group) >= 2]

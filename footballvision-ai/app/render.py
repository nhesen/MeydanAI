from __future__ import annotations

import cv2
import numpy as np

from app.core.config import AppConfig
from app.core.types import BallSample, PlayerTrack, TeamId

TEAM_BGR = {TeamId.HOME: (255, 175, 65), TeamId.AWAY: (90, 90, 255), TeamId.UNKNOWN: (180, 180, 180)}


def annotate_frame(
    frame: np.ndarray,
    tracks: dict[int, PlayerTrack],
    ball: BallSample,
    config: AppConfig,
) -> None:
    for track in tracks.values():
        sample = track.last
        if sample is None:
            continue
        color = TEAM_BGR[track.team]
        x1, y1, x2, y2 = (int(v) for v in sample.bbox.as_xyxy())
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = track.name or (f"#{track.jersey}" if track.jersey is not None else f"ID {track.track_id}")
        cv2.putText(frame, label, (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        if sample.with_ball:
            cv2.circle(frame, (int(sample.bbox.cx), int(sample.bbox.cy)), 7, (0, 255, 255), 2)
    if ball.pixel is not None:
        cv2.circle(frame, (int(ball.pixel[0]), int(ball.pixel[1])), 6, (0, 255, 255), -1)
        if ball.interpolated:
            cv2.circle(frame, (int(ball.pixel[0]), int(ball.pixel[1])), 10, (0, 180, 255), 1)
    cv2.putText(
        frame,
        f"{config.home_name} vs {config.away_name}",
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )


def write_minimap_frame(
    canvas: np.ndarray,
    tracks: dict[int, PlayerTrack],
    ball: BallSample,
    config: AppConfig,
) -> None:
    h, w = canvas.shape[:2]
    cv2.rectangle(canvas, (8, 8), (w - 8, h - 8), (40, 90, 40), -1)
    cv2.rectangle(canvas, (8, 8), (w - 8, h - 8), (230, 230, 230), 2)
    cv2.line(canvas, (w // 2, 8), (w // 2, h - 8), (230, 230, 230), 1)
    cv2.circle(canvas, (w // 2, h // 2), 28, (230, 230, 230), 1)
    for track in tracks.values():
        sample = track.last
        if sample is None or sample.world is None:
            continue
        x = 8 + int(sample.world[0] / config.pitch.length_m * (w - 16))
        y = 8 + int(sample.world[1] / config.pitch.width_m * (h - 16))
        cv2.circle(canvas, (x, y), 6, TEAM_BGR[track.team], -1)
        cv2.putText(canvas, str(track.track_id), (x + 6, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
    if ball.world is not None:
        x = 8 + int(ball.world[0] / config.pitch.length_m * (w - 16))
        y = 8 + int(ball.world[1] / config.pitch.width_m * (h - 16))
        cv2.circle(canvas, (x, y), 5, (0, 255, 255), -1)

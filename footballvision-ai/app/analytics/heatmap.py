from __future__ import annotations

from pathlib import Path

import numpy as np

from app.core.types import PlayerTrack, TeamId


def render_heatmap(
    tracks: list[PlayerTrack],
    path: Path,
    length_m: float,
    width_m: float,
    *,
    title: str = "",
) -> str:
    import cv2

    counts = np.zeros((360, 640), dtype=np.float32)
    for track in tracks:
        for sample in track.samples:
            if sample.world is None:
                continue
            x = sample.world[0] / length_m
            y = sample.world[1] / width_m
            if 0 <= x <= 1 and 0 <= y <= 1:
                counts[min(359, int(y * 360)), min(639, int(x * 640))] += 1
    density = cv2.GaussianBlur(counts, (0, 0), 14)
    scaled = (density / max(float(density.max()), 1e-9) * 255).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    cv2.rectangle(colored, (2, 2), (637, 357), (240, 240, 240), 1)
    cv2.line(colored, (320, 2), (320, 357), (240, 240, 240), 1)
    cv2.circle(colored, (320, 180), 42, (240, 240, 240), 1)
    if title:
        cv2.putText(colored, title, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), colored)
    return str(path)


def team_tracks(tracks: dict[int, PlayerTrack], team: TeamId) -> list[PlayerTrack]:
    return [track for track in tracks.values() if track.team is team]

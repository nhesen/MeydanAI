from __future__ import annotations

from pathlib import Path

import cv2

from app.core.config import AppConfig
from app.core.types import EventType, MatchEvent, PlayerTrack

HIGHLIGHT_TYPES = {
    EventType.GOAL,
    EventType.SHOT,
    EventType.SHOT_ON_TARGET,
    EventType.ASSIST,
    EventType.SAVE,
    EventType.TACKLE,
}


def cut_highlights(
    video_path: Path,
    events: list[MatchEvent],
    output_dir: Path,
    config: AppConfig,
    fps: float,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clips: list[dict] = []
    chosen = [event for event in events if event.event_type in HIGHLIGHT_TYPES]
    for index, event in enumerate(chosen):
        start = max(0.0, event.time_s - config.highlight_pre_s)
        end = event.time_s + config.highlight_post_s
        dest = output_dir / f"{index:03d}_{event.event_type.value}_{event.frame}.mp4"
        _extract(video_path, dest, start, end, fps)
        event.clip_path = str(dest)
        clips.append(
            {
                "path": str(dest),
                "event_type": event.event_type.value,
                "time_s": event.time_s,
                "player_id": event.player_id,
            }
        )
    return clips


def cut_player_clips(
    video_path: Path,
    tracks: dict[int, PlayerTrack],
    output_dir: Path,
    config: AppConfig,
    fps: float,
) -> dict[int, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[int, str] = {}
    for track in tracks.values():
        if len(track.samples) < 8:
            continue
        start = track.samples[0].time_s
        end = min(track.samples[-1].time_s, start + 12)
        dest = output_dir / f"player_{track.track_id}.mp4"
        _extract(video_path, dest, start, end, fps)
        paths[track.track_id] = str(dest)
    return paths


def _extract(source: Path, dest: Path, start: float, end: float, fps: float) -> None:
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        return
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    start_frame = int(start * fps)
    end_frame = int(end * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    index = start_frame
    while index <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        index += 1
    writer.release()
    cap.release()

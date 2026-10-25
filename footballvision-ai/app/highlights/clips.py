from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2

from app.core.config import AppConfig
from app.core.types import EventType, MatchEvent, PlayerTrack

HIGHLIGHT_TYPES = {
    EventType.GOAL,
    EventType.BIG_CHANCE,
}


def highlight_events(events: list[MatchEvent]) -> list[MatchEvent]:
    """Goals and big chances only. A chance that is the goal itself is one clip."""
    goal_times = [event.time_s for event in events if event.event_type is EventType.GOAL]
    return [
        event
        for event in events
        if event.event_type in HIGHLIGHT_TYPES
        and not (
            event.event_type is EventType.BIG_CHANCE
            and any(abs(event.time_s - goal_time) <= 2.0 for goal_time in goal_times)
        )
    ]


def cut_highlights(
    video_path: Path,
    events: list[MatchEvent],
    output_dir: Path,
    config: AppConfig,
    fps: float,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clips: list[dict] = []
    chosen = highlight_events(events)
    for index, event in enumerate(chosen):
        start = max(0.0, event.time_s - config.highlight_pre_s)
        end = event.time_s + config.highlight_post_s
        dest = output_dir / f"{index:03d}_{event.event_type.value}_{event.frame}.mp4"
        if not _extract(video_path, dest, start, end, fps):
            continue
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
        if _extract(video_path, dest, start, end, fps):
            paths[track.track_id] = str(dest)
    return paths


def _extract(source: Path, dest: Path, start: float, end: float, fps: float) -> bool:
    if end <= start:
        return False
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-ss",
                    f"{start:.3f}",
                    "-i",
                    str(source),
                    "-t",
                    f"{end - start:.3f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-an",
                    str(dest),
                ],
                capture_output=True,
                check=False,
                timeout=120,
            )
            if (
                completed.returncode == 0
                and dest.is_file()
                and dest.stat().st_size > 1000
            ):
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        cap.release()
        return False
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(dest), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        writer.release()
        cap.release()
        return False
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
    return index > start_frame and dest.is_file() and dest.stat().st_size > 1000

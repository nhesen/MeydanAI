from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from app.core.analytics_bounds import intensity_from_positions
from app.worker.analyzer import PlayerMotionResult, TrackSample

FOOTBALL_EVENT_TYPES = (
    "pass",
    "successful_pass",
    "failed_pass",
    "key_pass",
    "shot",
    "shot_on_target",
    "shot_off_target",
    "goal",
    "assist",
    "tackle",
    "interception",
    "turnover",
    "ball_recovery",
    "dribble",
    "save",
    "corner",
    "free_kick",
    "penalty",
)


def footballvision_root() -> Path:
    configured = os.environ.get("FOOTBALLVISION_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[3] / "footballvision-ai"


def analyze_with_footballvision(path: Path) -> list[PlayerMotionResult]:
    root = footballvision_root()
    if not root.is_dir():
        raise ValueError("FOOTBALLVISION_ROOT is not a directory")
    _ensure_football_weights(root)
    output_root = Path(os.environ.get("FOOTBALLVISION_OUTPUT", root / "var" / "footballvision-jobs"))
    if not output_root.is_absolute():
        output_root = (root / output_root).resolve()
    output = output_root / uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=True)
    print(
        f"footballvision device={os.environ.get('FOOTBALLVISION_DEVICE', 'auto')} image={os.environ.get('FOOTBALLVISION_IMAGE_SIZE', '640')}",
        flush=True,
    )
    config = os.environ.get(
        "FOOTBALLVISION_CONFIG",
        str(root / "configs" / "config.yaml"),
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    weights = root / "models" / "football-player-detection.pt"
    if weights.is_file():
        env["FOOTBALLVISION_MODEL"] = str(weights)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app",
            "--video",
            str(path),
            "--output",
            str(output),
            "--config",
            config,
        ],
        cwd=str(root),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr[-2000:] or "FOOTBALLVISION_FAILED")
    return load_motion_results(output)


def load_motion_results(output: Path) -> list[PlayerMotionResult]:
    tracks = json.loads((output / "tracks.json").read_text(encoding="utf-8"))
    events_by_player: dict[str, list[tuple[str, int, float | None, str]]] = {}
    events_path = output / "events.csv"
    if events_path.is_file() and events_path.stat().st_size:
        with events_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                player_id = row.get("player_id") or ""
                event_type = row.get("event_type") or "custom"
                stamp = int(float(row.get("time_s") or 0) * 1000)
                title = event_type.replace("_", " ")
                events_by_player.setdefault(player_id, []).append((event_type, stamp, None, title))
    stats: dict[str, dict[str, Any]] = {}
    stats_path = output / "player_stats.csv"
    if stats_path.is_file() and stats_path.stat().st_size:
        with stats_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                stats[row["player_id"]] = row
    results: list[PlayerMotionResult] = []
    for track_id, payload in tracks.items():
        positions = [
            TrackSample(
                timestamp_ms=int(point["timestamp_ms"]),
                x=float(point["x"]),
                y=float(point["y"]),
            )
            for point in payload.get("positions", [])
        ]
        if len(positions) < 2:
            continue
        row = stats.get(str(track_id), {})
        distance = _float(row.get("distance_m"))
        avg_speed = _float(row.get("avg_speed_kmh"))
        max_speed = _float(row.get("max_speed_kmh"))
        sprints = int(float(row.get("sprint_count") or 0))
        active = int(float(row.get("active_seconds") or 0))
        results.append(
            PlayerMotionResult(
                track_id=str(track_id),
                positions=positions,
                rating=_float(row.get("rating")) or 6.0,
                distance_m=distance or 0.0,
                avg_speed_kmh=avg_speed or 0.0,
                max_speed_kmh=max_speed or 0.0,
                sprint_count=sprints,
                active_seconds=max(active, 1),
                activity_count=len(positions),
                peak_speed_at_ms=positions[-1].timestamp_ms if max_speed else None,
                intensity=intensity_from_positions(positions),
                events=events_by_player.get(str(track_id), []),
                frame_width=1280,
                frame_height=720,
            )
        )
    return results


def _ensure_football_weights(root: Path) -> None:
    destination = root / "models" / "football-player-detection.pt"
    if destination.is_file() and destination.stat().st_size > 1_000_000:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        Path(__file__).resolve().parents[2] / "var" / "yolo-demo" / "models" / destination.name,
        Path(__file__).resolve().parents[3] / "backend" / "var" / "yolo-demo" / "models" / destination.name,
    ]
    for source in candidates:
        if source.is_file() and source.stat().st_size > 1_000_000:
            destination.write_bytes(source.read_bytes())
            return
    from app.demo.models import player_weights

    source = player_weights(root)
    if source.resolve() != destination.resolve() and source.is_file():
        destination.write_bytes(source.read_bytes())


def _float(value: Any) -> float | None:
    if value in {None, "", "None"}:
        return None
    return float(value)

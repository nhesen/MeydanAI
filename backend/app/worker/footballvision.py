from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import pairwise
from pathlib import Path
from typing import Any

from app.core.analytics_bounds import MAX_PLAUSIBLE_STEP_KMH, MAX_PLAYER_KMH, STANDING_KMH
from app.worker.analyzer import PlayerMotionResult, TrackSample
from app.worker.jersey_ocr import JerseyReader

_progress_callback: ContextVar[Callable[[int], None] | None] = ContextVar(
    "footballvision_progress", default=None
)
_calibration_config: ContextVar[dict[str, Any] | None] = ContextVar(
    "footballvision_calibration_config", default=None
)


@contextmanager
def analysis_progress(
    callback: Callable[[int], None], calibration_config: dict[str, Any] | None = None
) -> Iterator[None]:
    token = _progress_callback.set(callback)
    config_token = _calibration_config.set(calibration_config)
    try:
        yield
    finally:
        _progress_callback.reset(token)
        _calibration_config.reset(config_token)


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
    "goal_kick",
    "woodwork",
    "big_chance",
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
    configured_model = os.environ.get("FOOTBALLVISION_MODEL", "").strip()
    weights = _ensure_football_weights(root) if not configured_model else None
    output_root = Path(
        os.environ.get("FOOTBALLVISION_OUTPUT", root / "var" / "footballvision-jobs")
    )
    if not output_root.is_absolute():
        output_root = (root / output_root).resolve()
    output = output_root / uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=True)
    print(
        f"footballvision device={os.environ.get('FOOTBALLVISION_DEVICE', 'auto')} "
        f"image={os.environ.get('FOOTBALLVISION_IMAGE_SIZE', '640')}",
        flush=True,
    )
    config = os.environ.get(
        "FOOTBALLVISION_CONFIG",
        str(root / "configs" / "config.yaml"),
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    if weights is not None:
        env["FOOTBALLVISION_MODEL"] = str(weights)
    if not env.get("FOOTBALLVISION_BALL_MODEL"):
        try:
            env["FOOTBALLVISION_BALL_MODEL"] = str(_ensure_ball_weights(root))
        except (OSError, ValueError, TimeoutError) as exc:
            env["FOOTBALLVISION_BALL_MODEL"] = ""
            print(f"footballvision ball specialist unavailable: {exc}", flush=True)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    upload_config = _calibration_config.get() or {"mode": "relative"}
    calibration_file = output / "calibration-input.json"
    calibration_file.write_text(json.dumps(upload_config), encoding="utf-8")
    if upload_config.get("mode") == "automatic" and not env.get("FOOTBALLVISION_PITCH_MODEL"):
        env["FOOTBALLVISION_PITCH_MODEL"] = str(_ensure_pitch_weights(root))
    tail: deque[str] = deque(maxlen=25)
    callback = _progress_callback.get()
    last_progress = -1
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app",
            "--video",
            str(path.resolve()),
            "--output",
            str(output),
            "--config",
            config,
            "--calibration-json",
            str(calibration_file),
        ],
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    try:
        with (output / "analysis.log").open("w", encoding="utf-8") as log:
            assert process.stdout is not None
            for line in process.stdout:
                log.write(line)
                log.flush()
                tail.append(line)
                try:
                    message = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(message, dict) or "progress" not in message:
                    continue
                progress = max(0, min(100, int(message["progress"])))
                if callback is not None and progress >= last_progress + 2:
                    callback(progress)
                    last_progress = progress
        returncode = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        if process.stdout is not None:
            process.stdout.close()
    if returncode != 0:
        raise ValueError("".join(tail)[-2000:] or "FOOTBALLVISION_FAILED")
    return load_motion_results(output)


def load_motion_results(output: Path) -> list[PlayerMotionResult]:
    tracks = json.loads((output / "tracks.json").read_text(encoding="utf-8"))
    summary_path = output / "match_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    calibrated = (
        summary.get("calibrated", False) is True
        and isinstance(summary.get("calibration_coverage"), (int, float))
        and float(summary["calibration_coverage"]) >= 0.8
    )
    pitch_length = float(summary.get("pitch_length_m") or 40)
    pitch_width = float(summary.get("pitch_width_m") or 20)
    frame_width = int(summary.get("frame_width") or 1280)
    frame_height = int(summary.get("frame_height") or 720)
    events_by_player: dict[str, list[tuple[str, int, float | None, str]]] = {}
    media_by_player: dict[str, dict[int, dict[str, Any]]] = {}
    events_path = output / "events.csv"
    if events_path.is_file() and events_path.stat().st_size:
        with events_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                player_id = row.get("player_id") or ""
                event_type = row.get("event_type") or "custom"
                extra = _event_extra(row.get("extra"))
                if extra.get("estimated") or not calibrated:
                    continue
                stamp = int(float(row.get("time_s") or 0) * 1000)
                title = "Possible " + event_type.replace("_", " ")
                if isinstance(extra.get("xg"), (int, float)):
                    title = f"{title} · xG {float(extra['xg']):.2f}"
                events_by_player.setdefault(player_id, []).append((event_type, stamp, None, title))
                clip_path = row.get("clip_path")
                if clip_path:
                    media = _publish_clip(output, Path(clip_path))
                    if media is not None:
                        media_by_player.setdefault(player_id, {})[stamp] = media
    stats: dict[str, dict[str, Any]] = {}
    stats_path = output / "player_stats.csv"
    if stats_path.is_file() and stats_path.stat().st_size:
        with stats_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                stats[row["player_id"]] = row
    results: list[PlayerMotionResult] = []
    reader = JerseyReader(enabled=os.environ.get("FOOTBALLVISION_JERSEY_OCR", "1") != "0")
    for track_id, payload in tracks.items():
        if payload.get("role") not in {None, "player", "goalkeeper"}:
            continue
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
        raw_points = payload.get("positions", [])
        metric_points = [point for point in raw_points if point.get("calibrated", calibrated)]
        distance = _float(row.get("distance_m"))
        avg_speed = _float(row.get("avg_speed_kmh"))
        max_speed = _float(row.get("max_speed_kmh"))
        peak_at = _float(row.get("peak_speed_at_ms"))
        measured_seconds = float(row.get("measured_seconds") or 0)
        track_calibrated = (
            calibrated
            and bool(metric_points)
            and distance is not None
            and measured_seconds >= 8
        )
        sprints = int(float(row.get("sprint_count") or 0)) if track_calibrated else None
        observed_seconds = (positions[-1].timestamp_ms - positions[0].timestamp_ms) / 1000
        active = math.ceil(float(row.get("active_seconds") or observed_seconds))
        intensity = []
        if track_calibrated:
            if "intensity" in payload:
                intensity = [
                    (int(item["from_minute"]), int(item["to_minute"]), float(item["intensity"]))
                    for item in payload["intensity"]
                ]
            else:
                intensity = _calibrated_intensity(raw_points, pitch_length, pitch_width, calibrated)
        evidence = _track_evidence(output, payload, positions, reader)
        results.append(
            PlayerMotionResult(
                track_id=str(track_id),
                positions=positions,
                rating=_float(row.get("rating")) if track_calibrated else None,
                distance_m=distance if track_calibrated else None,
                avg_speed_kmh=avg_speed if track_calibrated else None,
                max_speed_kmh=max_speed if track_calibrated else None,
                sprint_count=sprints,
                active_seconds=max(active, 1),
                activity_count=len(positions),
                peak_speed_at_ms=int(peak_at) if track_calibrated and peak_at is not None else None,
                intensity=intensity,
                events=events_by_player.get(str(track_id), []),
                frame_width=frame_width,
                frame_height=frame_height,
                team=payload.get("team"),
                jersey_number=(
                    int(payload["jersey"])
                    if payload.get("jersey") is not None
                    else evidence.get("jersey_candidate")
                ),
                calibration={
                    "version": "footballvision-v2",
                    "source_frame_width": frame_width,
                    "source_frame_height": frame_height,
                    "pitch_length_m": pitch_length,
                    "pitch_width_m": pitch_width,
                    "transform_metadata": {
                        "method": str(summary.get("calibration_source", "estimated")),
                        "calibrated": track_calibrated,
                        "calibration_coverage": float(
                            payload.get(
                                "calibration_coverage", len(metric_points) / max(len(raw_points), 1)
                            )
                        ),
                        "measured_seconds": float(row.get("measured_seconds") or 0),
                        "identity_mapping": "team-and-activity-estimate",
                        **{
                            key: value
                            for key, value in {
                                "ball_observed_coverage": summary.get("ball_observed_coverage"),
                                "sprint_threshold_kmh": (
                                    summary.get("sprint_definition") or {}
                                ).get("threshold_kmh"),
                                "sprint_min_duration_s": (
                                    summary.get("sprint_definition") or {}
                                ).get("minimum_duration_s"),
                            }.items()
                            if value is not None
                        },
                    },
                },
                event_media=media_by_player.get(str(track_id), {}),
                track_evidence=evidence or None,
            )
        )
    return results


def _publish_clip(output: Path, source: Path) -> dict[str, Any] | None:
    source = (output / source).resolve() if not source.is_absolute() else source.resolve()
    if not source.is_relative_to(output.resolve()) or not source.is_file():
        return None
    if source.suffix.lower() != ".mp4":
        return None
    storage = Path(os.environ.get("VIDEO_STORAGE_PATH", "./var/videos")) / "highlights"
    storage.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.mp4"
    shutil.copyfile(source, storage / name)
    return {"video_url": f"/api/v1/public/media/highlights/{name}"}


def _calibrated_intensity(
    points: list[dict[str, Any]], length_m: float, width_m: float, default_calibrated: bool
) -> list[tuple[int, int, float]]:
    """Only consecutive measured intervals contribute; missing calibration is a break."""
    buckets: dict[int, list[tuple[float, int]]] = {}
    for previous, current in pairwise(points):
        if not previous.get("calibrated", default_calibrated) or not current.get(
            "calibrated", default_calibrated
        ):
            continue
        if previous.get("segment_id") != current.get("segment_id"):
            continue
        start, end = int(previous["timestamp_ms"]), int(current["timestamp_ms"])
        duration = end - start
        if not 0 < duration <= 1000:
            continue
        speed = (
            math.hypot(
                (float(current["x"]) - float(previous["x"])) * length_m,
                (float(current["y"]) - float(previous["y"])) * width_m,
            )
            / (duration / 1000)
            * 3.6
        )
        if not math.isfinite(speed) or speed > MAX_PLAUSIBLE_STEP_KMH:
            continue
        speed = 0.0 if speed < STANDING_KMH else min(speed, MAX_PLAYER_KMH)
        while start < end:
            minute = start // 60_000
            limit = min(end, (minute + 1) * 60_000)
            buckets.setdefault(minute, []).append((speed, limit - start))
            start = limit
    return [
        (
            minute,
            minute + 1,
            round(
                100
                * sum(speed * duration for speed, duration in intervals)
                / sum(duration for _, duration in intervals)
                / MAX_PLAYER_KMH,
                1,
            ),
        )
        for minute, intervals in sorted(buckets.items())
    ]


def _contained_file(output: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    candidate = candidate.resolve() if candidate.is_absolute() else (output / candidate).resolve()
    if not candidate.is_relative_to(output.resolve()) or not candidate.is_file():
        return None
    return candidate


def _track_evidence(
    output: Path, payload: dict[str, Any], positions: list[TrackSample], reader: JerseyReader
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "first_seen_ms": int(payload.get("first_seen_ms", positions[0].timestamp_ms)),
        "last_seen_ms": int(payload.get("last_seen_ms", positions[-1].timestamp_ms)),
    }
    images = []
    for item in payload.get("evidence_images", [])[:3]:
        path = _contained_file(output, item.get("path"))
        if path is not None:
            images.append((path, int(item["timestamp_ms"])))
    image_path = _contained_file(output, payload.get("image_path"))
    image_path = image_path or (images[0][0] if images else None)
    if image_path is not None and image_path.suffix.lower() in {".jpg", ".png"}:
        storage = Path(os.environ.get("VIDEO_STORAGE_PATH", "./var/videos")) / "tracks"
        storage.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + image_path.suffix.lower()
        shutil.copyfile(image_path, storage / name)
        evidence["image_url"] = f"/api/v1/public/media/tracks/{name}"
    evidence.update(reader.read(images))
    return evidence


def _ensure_pitch_weights(root: Path) -> Path:
    destination = root / "models" / "football-pitch-detection.pt"
    if destination.is_file() and destination.stat().st_size > 1_000_000:
        return destination
    source = Path(__file__).resolve().parents[2] / "var" / "yolo-demo" / "models" / destination.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.stat().st_size > 1_000_000:
        shutil.copyfile(source, destination)
        return destination
    from app.demo.models import pitch_weights

    source = pitch_weights(root)
    if source.resolve() != destination.resolve():
        shutil.copyfile(source, destination)
    return destination


def _ensure_football_weights(root: Path) -> Path | None:
    """Return local player weights, or None so analysis can use YOLO11n."""
    destination = root / "models" / "football-player-detection.pt"
    if destination.is_file() and destination.stat().st_size > 1_000_000:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        Path(__file__).resolve().parents[2] / "var" / "yolo-demo" / "models" / destination.name,
        Path(__file__).resolve().parents[3]
        / "backend"
        / "var"
        / "yolo-demo"
        / "models"
        / destination.name,
    ]
    for source in candidates:
        if source.is_file() and source.stat().st_size > 1_000_000:
            destination.write_bytes(source.read_bytes())
            return destination
    try:
        from app.demo.models import player_weights

        source = player_weights(root)
    except (OSError, ValueError, TimeoutError) as exc:
        print(f"footballvision player weights unavailable, using yolo11n: {exc}", flush=True)
        return None
    if source.resolve() != destination.resolve() and source.is_file():
        destination.write_bytes(source.read_bytes())
    return destination if destination.is_file() else None


def _event_extra(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _float(value: Any) -> float | None:
    if value in {None, "", "None"}:
        return None
    return float(value)


def _ensure_ball_weights(root: Path) -> Path:
    """Pinned, checksum-verified specialist; no unverified replacement on failure."""
    import hashlib
    import urllib.request

    destination = root / "models" / "football-ball-specialist.pt"
    expected = "fb37942448e7de08745e8aab148d0794f680a738ddd55e5f17abe9ab2d6313fb"
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = "https://huggingface.co/martinjolif/yolo-football-ball-detection/resolve/main/yolo-football-ball-detection.pt"
    with urllib.request.urlopen(url, timeout=120) as response:
        content = response.read(20_000_000)
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Ball model checksum mismatch")
    temporary = destination.with_suffix(".download")
    temporary.write_bytes(content)
    temporary.replace(destination)
    return destination

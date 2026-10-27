from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.analytics.heatmap import render_heatmap, team_tracks
from app.analytics.physics import motion_intensity
from app.analytics.stats import build_player_stats, build_team_stats
from app.calibration.camera import CameraCompensator
from app.calibration.homography import (
    PitchMapper,
    detect_visible_pitch,
    pitch_outline,
    trusted_visible_pitch,
)
from app.calibration.keypoints import KeypointCalibrator
from app.calibration.zones import PitchZones
from app.core.config import AppConfig, load_config
from app.core.types import (
    BallSample,
    Detection,
    MatchResult,
    PlayerTrack,
    Role,
    TeamId,
    TrackSample,
)
from app.detection.yolo import FootballDetector
from app.events.detector import EventDetector
from app.highlights.clips import cut_highlights, cut_player_clips
from app.render import annotate_frame, write_minimap_frame
from app.reports.evidence import PlayerEvidence
from app.reports.exporters import export_tables
from app.reports.html_report import write_html_report
from app.tracking.ball_tracker import BallTracker
from app.tracking.player_tracker import PlayerTracker
from app.tracking.reid import IdentityRepair
from app.tracking.teams import TeamAssigner, lab_median, torso_hist

Progress = Callable[[int, str], None]


def measurement_is_trusted(valid_frames: int, processed_frames: int) -> bool:
    """A few fitted frames are not a measured match."""
    if processed_frames < 8 or valid_frames < 8:
        return False
    return valid_frames / processed_frames >= 0.8


def analyze_video(
    video_path: str | Path,
    output_dir: str | Path,
    config: AppConfig | None = None,
    *,
    calibration_points: list[tuple[float, float]] | None = None,
    progress: Progress | None = None,
) -> MatchResult:
    cfg = config or load_config()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = progress or (lambda _pct, _msg: None)
    report(2, "video açılır")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Video could not be decoded.")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25)
    total_frames = max(cap.get(cv2.CAP_PROP_FRAME_COUNT), 1)
    if not np.isfinite(fps) or fps <= 0:
        fps = 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        cap.release()
        raise ValueError("Video has invalid frame dimensions.")
    frame_stride = max(
        1, int(os.environ.get("FOOTBALLVISION_FRAME_STRIDE", "1") or "1")
    )
    batch_size = max(1, int(os.environ.get("FOOTBALLVISION_BATCH", "8") or "8"))
    output_fps = fps / frame_stride
    detector = FootballDetector(cfg)
    tracker = PlayerTracker(cfg, frame_rate=output_fps)
    ball_tracker = BallTracker(cfg)
    teams = TeamAssigner()
    camera_mode = (
        "on"
        if cfg.compensate_camera or cfg.camera_mode == "broadcast"
        else cfg.camera_mode
    )
    camera = CameraCompensator(
        enabled=camera_mode == "on",
        mode=camera_mode if camera_mode in {"on", "auto", "off"} else "off",
    )
    mapper: PitchMapper | None = None
    points = calibration_points or list(
        map(tuple, cfg.raw.get("calibration", {}).get("points", []))
    )
    calibration_mode = str(
        cfg.raw.get("calibration", {}).get("mode")
        or ("manual" if points else "relative")
    )
    if calibration_mode == "relative":
        points = []
    keypoint_calibrator = (KeypointCalibrator(cfg) if calibration_mode == "automatic"
                          and cfg.pitch.mode == "11v11" and cfg.detection.pitch_model else None)
    calibration_frames: list[dict[str, Any]] = []
    evidence = PlayerEvidence(out / "player_crops")
    render_video = os.environ.get("FOOTBALLVISION_RENDER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    annotated = out / "annotated_raw.mp4"
    minimap = out / "minimap_raw.mp4"
    writer = (
        cv2.VideoWriter(
            str(annotated), cv2.VideoWriter_fourcc(*"mp4v"), output_fps, (width, height)
        )
        if render_video
        else None
    )
    radar = (
        cv2.VideoWriter(
            str(minimap), cv2.VideoWriter_fourcc(*"mp4v"), output_fps, (640, 360)
        )
        if render_video
        else None
    )
    if render_video and (not writer.isOpened() or not radar.isOpened()):
        cap.release()
        writer.release()
        radar.release()
        raise ValueError("The annotated video output could not be created.")
    tracks: dict[int, PlayerTrack] = {}
    frame_index = 0
    pending: list[tuple[int, np.ndarray]] = []
    segment_id = 0
    had_scene_cut = False
    last_team_fit = 0.0
    last_progress = -1

    def consume(index: int, frame: np.ndarray, raw: list[Detection]) -> None:
        nonlocal mapper, segment_id, had_scene_cut, last_team_fit, last_progress
        time_s = index / fps
        outline = pitch_outline(frame)
        if outline is not None:
            margin = max(4.0, width * 0.005)
            raw = [
                item
                for item in raw
                if item.role is Role.BALL
                or cv2.pointPolygonTest(outline, item.bbox.foot(), True) >= -margin
            ]
        camera.update(frame, [item.bbox.as_xyxy() for item in raw])
        if camera.scene_cut:
            had_scene_cut = True
            segment_id += 1
            tracker.reset()
            ball_tracker.cut()
            mapper = None
        relative_mapper = _init_mapper(frame, cfg, width, height, [])
        source = "relative"
        quality: dict[str, Any] = {"valid": False, "source": source, "reason": "no_metric_calibration"}
        use_camera_reference = False
        if keypoint_calibrator is not None:
            fitted = keypoint_calibrator.calibrate(frame)
            mapper, quality = fitted.mapper, fitted.quality
            source = "pitch-keypoints" if mapper is not None else "relative"
        elif calibration_mode == "manual" and points and not had_scene_cut:
            if mapper is None:
                mapper = _init_mapper(frame, cfg, width, height, points)
            use_camera_reference = camera.enabled
            # Translation-only compensation cannot certify a moving perspective.
            valid = not camera.enabled
            quality = {"valid": valid, "source": "manual", "reason": None if valid else "moving_manual_camera_requires_keypoints"}
            source = "manual" if valid else "relative"
        else:
            mapper = None
        if mapper is None and calibration_mode != "manual":
            visible = trusted_visible_pitch(frame, cfg)
            if visible is not None:
                mapper = visible
                source = "visible-pitch"
                quality = {"valid": True, "source": source, "reason": None}
        metric_frame = bool(mapper and mapper.calibrated and quality["valid"])
        calibration_frames.append({"frame": index, "timestamp_ms": round(time_s*1000), **quality})

        def map_point(x: float, y: float) -> tuple[tuple[float, float] | None, bool]:
            reference = camera.warp_point(x, y) if use_camera_reference else (x, y)
            world = mapper.to_world(*reference) if metric_frame and mapper is not None else None
            return (world, True) if world is not None else (relative_mapper.to_world(x, y), False)
        detections = raw
        if not detections or not all(
            item.track_id is not None or item.role is Role.BALL for item in detections
        ):
            detections = tracker.update(detections, frame.shape[:2])
        people = [item for item in detections if item.role is not Role.BALL]
        for detection in people:
            if detection.track_id is None:
                continue
            pixel = detection.bbox.foot()
            world, metric_sample = map_point(*pixel)
            evidence.observe(frame, detection, index, time_s)
            known = teams.features.get(detection.track_id, [])
            hist = torso_hist(frame, detection.bbox) if len(known) < 16 else None
            feature = lab_median(frame, detection.bbox) if len(known) < 16 else None
            teams.observe(detection.track_id, feature, detection.role)
            track = tracks.setdefault(
                detection.track_id,
                PlayerTrack(
                    track_id=detection.track_id,
                    role=detection.role,
                    segment_id=segment_id,
                ),
            )
            if detection.role is Role.GOALKEEPER:
                track.role = Role.GOALKEEPER
            track.team = teams.team(detection.track_id)
            track.samples.append(
                TrackSample(
                    frame=index,
                    time_s=time_s,
                    pixel=pixel,
                    bbox=detection.bbox,
                    world=world,
                    confidence=detection.confidence,
                    team=track.team,
                    role=track.role,
                    color_hist=hist,
                    calibrated=metric_sample,
                    calibration_source=source if metric_sample else "relative",
                )
            )
        if time_s - last_team_fit >= 2.0:
            teams.fit()
            last_team_fit = time_s
        ball = ball_tracker.update(
            detections,
            index,
            time_s,
            lambda x, y: map_point(x, y)[0],
            calibrated=metric_frame,
            calibration_source=source,
        )
        if ball.pixel is not None and not map_point(*ball.pixel)[1]:
            ball.calibrated = False
            ball.calibration_source = "relative"
            ball.velocity_mps = None
        live_tracks = {
            key: track
            for key, track in tracks.items()
            if track.last and track.last.frame == index
        }
        for track in live_tracks.values():
            if track.last and ball.world and track.last.world:
                dist = (
                    (ball.world[0] - track.last.world[0]) ** 2
                    + (ball.world[1] - track.last.world[1]) ** 2
                ) ** 0.5
                track.last.with_ball = dist <= cfg.events.possession_radius_m
        if writer is not None and radar is not None:
            annotate_frame(frame, live_tracks, ball, cfg)
            writer.write(frame)
            radar_frame = np.zeros((360, 640, 3), dtype=np.uint8)
            write_minimap_frame(radar_frame, live_tracks, ball, cfg)
            radar.write(radar_frame)
        percent = min(80, 5 + int(70 * index / total_frames))
        if percent > last_progress:
            last_progress = percent
            report(
                percent,
                "izləmə",
            )

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        found = detector.detect_many([item[1] for item in pending])
        for (index, stored), raw in zip(pending, found, strict=True):
            consume(index, stored, raw)
        pending = []

    frame_source = _prefetched_frames(cap)
    try:
        for frame in frame_source:
            if frame_index % frame_stride != 0:
                frame_index += 1
                continue
            pending.append((frame_index, frame))
            frame_index += 1
            if len(pending) >= batch_size:
                flush()
        flush()
    finally:
        frame_source.close()
        cap.release()
        if writer is not None:
            writer.release()
        if radar is not None:
            radar.release()
    if frame_index == 0:
        raise ValueError("The video contains no decodable frames.")
    if teams.centers is None:
        teams.fit()
    for track in tracks.values():
        track.team = teams.team(track.track_id)
        for sample in track.samples:
            sample.team = track.team
    report(82, "ID bərpası")
    tracks = IdentityRepair(cfg).merge(tracks)
    # Two-frame flashes and signs are not reliable player observations.
    tracks = {key: track for key, track in tracks.items() if len(track.samples) >= 3}
    result = finalize_match(
        tracks,
        ball_tracker.samples,
        cfg,
        output_dir=out,
        video_path=Path(video_path),
        fps=fps,
        frame_count=frame_index,
        frame_width=width,
        frame_height=height,
        calibrated=measurement_is_trusted(
            sum(bool(item["valid"]) for item in calibration_frames),
            len(calibration_frames),
        ),
        annotated_video=annotated if render_video else None,
        minimap_video=minimap if render_video else None,
        progress=report,
        calibration_source="pitch-keypoints" if keypoint_calibrator else "manual" if points else "relative",
        calibration_frames=calibration_frames,
        evidence=evidence,
    )
    return result


def analyze_observations(
    tracks: dict[int, PlayerTrack],
    ball: list[BallSample],
    config: AppConfig,
    output_dir: str | Path,
    *,
    fps: float = 25.0,
    frame_width: int = 1280,
    frame_height: int = 720,
    calibrated: bool = True,
    video_path: Path | None = None,
) -> MatchResult:
    return finalize_match(
        tracks,
        ball,
        config,
        output_dir=Path(output_dir),
        video_path=video_path,
        fps=fps,
        frame_count=max((sample.frame for sample in ball), default=0) + 1,
        frame_width=frame_width,
        frame_height=frame_height,
        calibrated=calibrated,
        annotated_video=None,
        minimap_video=None,
    )


def finalize_match(
    tracks: dict[int, PlayerTrack],
    ball: list[BallSample],
    config: AppConfig,
    *,
    output_dir: Path,
    video_path: Path | None,
    fps: float,
    frame_count: int,
    frame_width: int,
    frame_height: int,
    calibrated: bool,
    annotated_video: Path | None,
    minimap_video: Path | None,
    progress: Progress | None = None,
    calibration_source: str | None = None,
    calibration_frames: list[dict[str, Any]] | None = None,
    evidence: PlayerEvidence | None = None,
) -> MatchResult:
    report = progress or (lambda _pct, _msg: None)
    zones = PitchZones.from_config(config)
    if not calibrated:
        for item in ball:
            item.calibrated = False
        for track in tracks.values():
            for item in track.samples:
                item.calibrated = False
    (output_dir / "player_observations.json").write_text(json.dumps({key: asdict(value) for key, value in tracks.items()}), encoding="utf-8")
    detector = EventDetector(config, zones)
    track_by_frame: dict[int, dict[int, PlayerTrack]] = {}
    for track in tracks.values():
        for sample in track.samples:
            snapshot = track_by_frame.setdefault(sample.frame, {})
            view = PlayerTrack(
                track.track_id, track.role, track.team, track.jersey, track.name
            )
            view.samples = [sample]
            snapshot[track.track_id] = view
    for sample in ball:
        live = track_by_frame.get(sample.frame, {})
        live_tracks = live
        detector.update(sample, live_tracks)
        last_live = live_tracks
        last_ball = sample
    if ball:
        detector.flush(last_ball, last_live)
    if not calibrated:
        for event in detector.events:
            event.extra["estimated"] = True
            event.extra["calibration_source"] = calibration_source or "estimated"
    report(88, "statistikalar")
    players = build_player_stats(
        tracks,
        detector.events,
        detector.possession.state.player_frames,
        sum(detector.possession.state.team_frames.values()),
        config,
        zones,
        sample_period_s=float(np.median(np.diff([item.time_s for item in ball])))
        if len(ball) > 1
        else 1 / fps,
        calibrated=calibrated,
    )
    teams = build_team_stats(players, detector.events)
    home_goals = next((item.goals for item in teams if item.team is TeamId.HOME), 0)
    away_goals = next((item.goals for item in teams if item.team is TeamId.AWAY), 0)
    heat_dir = output_dir / "heatmaps"
    heatmaps = {
        "home": render_heatmap(
            team_tracks(tracks, TeamId.HOME),
            heat_dir / "home.png",
            config.pitch.length_m,
            config.pitch.width_m,
            title="Home",
        ),
        "away": render_heatmap(
            team_tracks(tracks, TeamId.AWAY),
            heat_dir / "away.png",
            config.pitch.length_m,
            config.pitch.width_m,
            title="Away",
        ),
    }
    for player in players:
        heatmaps[str(player.track_id)] = render_heatmap(
            [tracks[player.track_id]],
            heat_dir / f"player_{player.track_id}.png",
            config.pitch.length_m,
            config.pitch.width_m,
            title=player.name or f"ID {player.track_id}",
        )
        player.heatmap_path = heatmaps[str(player.track_id)]
    highlights: list[dict[str, Any]] = []
    if video_path is not None:
        report(92, "highlight kliplər")
        highlights = cut_highlights(
            video_path, detector.events, output_dir / "highlights", config, fps
        )
        player_clips = {}
        if os.environ.get("FOOTBALLVISION_PLAYER_CLIPS", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }:
            player_clips = cut_player_clips(
                video_path, tracks, output_dir / "highlights" / "players", config, fps
            )
        for player in players:
            player.highlight_path = player_clips.get(player.track_id)
    report(96, "hesabat")
    metadata = {
        "fps": fps,
        "frame_count": frame_count,
        "duration_s": round(frame_count / fps, 3),
        "frame_width": frame_width,
        "frame_height": frame_height,
        "pitch_length_m": config.pitch.length_m,
        "pitch_width_m": config.pitch.width_m,
        "calibrated": calibrated,
        "calibration_source": calibration_source
        or ("manual" if calibrated else "relative"),
        "model": config.detection.model,
        "device": config.detection.device,
        "physical_metrics_available": any(item.distance_m is not None for item in players),
    }
    if calibration_frames is not None:
        valid_frames = [item for item in calibration_frames if item["valid"]]
        reprojections = [item["reprojection_rmse_px"] for item in valid_frames if "reprojection_rmse_px" in item]
        metadata["calibration_coverage"] = round(len(valid_frames)/max(1, len(calibration_frames)), 4)
        metadata["calibration_quality"] = {
            "valid_frames": len(valid_frames), "processed_frames": len(calibration_frames),
            "median_reprojection_rmse_px": round(float(np.median(reprojections)), 3) if reprojections else None,
            "failure_reasons": dict(Counter(item.get("reason") for item in calibration_frames if not item["valid"])),
        }
        (output_dir / "calibration_frames.json").write_text(json.dumps(calibration_frames), encoding="utf-8")
    metadata["ball_observed_coverage"] = round(sum(item.pixel is not None and not item.interpolated for item in ball) / max(1, len(ball)), 4)
    metadata["sprint_definition"] = {"threshold_kmh": config.tracking.sprint_kmh, "minimum_duration_s": config.tracking.sprint_min_duration_s, "hysteresis_kmh": config.tracking.sprint_hysteresis_kmh}
    (output_dir / "ball_observations.json").write_text(json.dumps([asdict(item) for item in ball]), encoding="utf-8")
    (output_dir / "possession_timeline.json").write_text(json.dumps(detector.possession.state.timeline), encoding="utf-8")
    tables = export_tables(
        output_dir,
        players,
        teams,
        detector.events,
        detector.possession.percentages(),
        metadata,
    )
    _write_tracks_json(output_dir / "tracks.json", tracks, config, {item.track_id: item for item in players}, evidence)
    result = MatchResult(
        fps=fps,
        frame_count=frame_count,
        duration_s=round(frame_count / max(fps, 1e-6), 3),
        frame_width=frame_width,
        frame_height=frame_height,
        pitch_length_m=config.pitch.length_m,
        pitch_width_m=config.pitch.width_m,
        calibrated=calibrated,
        home_name=config.home_name,
        away_name=config.away_name,
        score=(home_goals, away_goals),
        players=players,
        teams=teams,
        events=detector.events,
        tracks=tracks,
        ball=ball,
        possession_timeline=detector.possession.state.timeline,
        heatmaps=heatmaps,
        highlights=highlights,
        annotated_video=None if annotated_video is None else str(annotated_video),
        minimap_video=None if minimap_video is None else str(minimap_video),
        report_html=None,
        report_pdf=None,
        extras={
            "tables": tables,
            "possession": detector.possession.percentages(),
            "analysis": metadata,
        },
    )
    result.report_html = write_html_report(output_dir / "match_report.html", result)
    return result


def _prefetched_frames(cap: cv2.VideoCapture, depth: int = 8):
    """Decode ahead on a worker thread so the GPU is not idle during video decode."""
    import queue
    import threading

    frames: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=depth)
    stop = threading.Event()

    def reader() -> None:
        try:
            while not stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                while not stop.is_set():
                    try:
                        frames.put(frame, timeout=0.2)
                        break
                    except queue.Full:
                        continue
        finally:
            while not stop.is_set():
                try:
                    frames.put(None, timeout=0.2)
                    break
                except queue.Full:
                    continue

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        while (frame := frames.get()) is not None:
            yield frame
    finally:
        stop.set()
        thread.join(timeout=5)


def _init_mapper(
    frame: np.ndarray,
    config: AppConfig,
    width: int,
    height: int,
    points: list[tuple[float, float]],
) -> PitchMapper:
    if len(points) == 4:
        return PitchMapper.from_points(points, config, width, height)
    detected = detect_visible_pitch(frame)
    if detected is None:
        mapper = PitchMapper(
            config.pitch.length_m,
            config.pitch.width_m,
            frame_width=width,
            frame_height=height,
        )
        return mapper
    mapper = PitchMapper.from_points(detected, config, width, height)
    mapper.estimated = True
    return mapper


def _read_detections(
    detector: FootballDetector, tracker: PlayerTracker, frame: np.ndarray
) -> list[Detection]:
    detections = detector.detect(frame)
    if detections and all(
        item.track_id is not None or item.role is Role.BALL for item in detections
    ):
        return detections
    return tracker.update(detections, frame.shape[:2])


def _write_tracks_json(
    path: Path, tracks: dict[int, PlayerTrack], config: AppConfig,
    player_stats: dict[int, Any] | None = None,
    evidence: PlayerEvidence | None = None,
) -> None:
    import json

    payload = {}
    for track_id, track in tracks.items():
        if track.role not in {Role.PLAYER, Role.GOALKEEPER}:
            continue
        points = []
        for sample in track.samples:
            if sample.world is None:
                continue
            points.append(
                {
                    "timestamp_ms": int(sample.time_s * 1000),
                    "x": round(sample.world[0] / config.pitch.length_m, 4),
                    "y": round(sample.world[1] / config.pitch.width_m, 4),
                    "calibrated": sample.calibrated,
                    "calibration_source": sample.calibration_source,
                    "segment_id": track.segment_id,
                }
            )
        payload[str(track_id)] = {
            "team": track.team.value,
            "role": track.role.value,
            "jersey": track.jersey,
            "name": track.name,
            "positions": points[:: max(1, len(points) // 400)] if points else [],
            "first_seen_ms": round(track.samples[0].time_s*1000) if track.samples else None,
            "last_seen_ms": round(track.samples[-1].time_s*1000) if track.samples else None,
            "calibration_coverage": round(sum(item.calibrated for item in track.samples)/max(1, len(track.samples)), 4),
            "measured_seconds": getattr((player_stats or {}).get(track_id), "measured_seconds", 0.0),
            "physical_metrics_available": getattr((player_stats or {}).get(track_id), "distance_m", None) is not None,
            "quality": {
                "observation_count": len(track.samples),
                "metric_observation_count": sum(item.calibrated for item in track.samples),
                "calibration_sources": sorted({item.calibration_source for item in track.samples}),
                "identity_confirmed": False,
                "speed_window_s": 0.4,
            },
            "intensity": motion_intensity(track, config),
            **(evidence.for_track(track) if evidence else {"image_path": None, "evidence_images": []}),
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


def apply_manual_corrections(
    tracks: dict[int, PlayerTrack], corrections: dict[str, Any]
) -> None:
    for raw_id, payload in corrections.items():
        track = tracks.get(int(raw_id))
        if track is None:
            continue
        if "team" in payload:
            track.team = TeamId(payload["team"])
        if "jersey" in payload:
            track.jersey = payload["jersey"]
        if "name" in payload:
            track.name = payload["name"]
        if "role" in payload:
            track.role = Role(payload["role"])

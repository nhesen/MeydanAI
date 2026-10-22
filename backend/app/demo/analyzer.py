# Azerbaijani UI messages intentionally contain the dotless letter U+0131.
# ruff: noqa: RUF001
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2

from app.demo.camera import CameraRegistration
from app.demo.football import (
    TEAM_COLORS,
    JerseyGroups,
    adjust_visible_length,
    field_region,
    heatmap,
    on_field,
    role_classes,
    shirt_feature,
    visible_pitch_points,
)
from app.demo.metrics import Calibration, ground_point, summarize_track
from app.demo.models import PITCH_NAME, pitch_weights, player_weights
from app.demo.pitch import calibration_from_keypoint_result


def analyze(
    source: Path,
    directory: Path,
    calibration: Calibration | None,
    progress: Callable[[int, str], None],
) -> dict[str, Any]:
    os.environ.setdefault("YOLO_CONFIG_DIR", str(directory.parent / ".ultralytics"))
    Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
    from ultralytics.models import YOLO

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ValueError("FFmpeg is required to produce browser-compatible video.")
    cap = cv2.VideoCapture(str(source))
    writer = None
    started = time.monotonic()
    try:
        if not cap.isOpened():
            raise ValueError("Video could not be decoded. Upload an MP4, MOV or WebM file.")
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width, height = (
            int(cap.get(prop)) for prop in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT)
        )
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or not 1 <= fps <= 120 or min(width, height) <= 0:
            raise ValueError("The video has invalid dimensions or frame rate.")
        max_seconds = int(os.environ.get("DEMO_MAX_SECONDS", "180"))
        if total_frames > fps * max_seconds + 1:
            raise ValueError(f"Use a clip no longer than {max_seconds} seconds for this demo.")
        progress(1, "Futbol oyunçu və meydança modelləri hazırlanır")
        storage = directory.parent
        requested = os.environ.get("DEMO_YOLO_MODEL")
        weights = requested or str(player_weights(storage))
        model = YOLO(weights)  # Fresh tracker for every job; no IDs leaked between clips.
        person_classes, referee_classes, ball_classes = role_classes(model.names)
        if not person_classes:
            raise ValueError("Model must have person, player or goalkeeper labels.")
        device = os.environ.get("DEMO_DEVICE", "cpu")
        image_size = int(os.environ.get("DEMO_IMAGE_SIZE", "1280"))
        pitch_model = YOLO(os.environ.get("DEMO_PITCH_MODEL") or str(pitch_weights(storage)))
        scale = min(1.0, 1280 / width)
        output_size = (int(width * scale) // 2 * 2, int(height * scale) // 2 * 2)
        raw_video = directory / "annotated-raw.mp4"
        writer = cv2.VideoWriter(str(raw_video), cv2.VideoWriter.fourcc(*"mp4v"), fps, output_size)
        if not writer.isOpened():
            raise ValueError("Video encoder could not be opened.")
        transform = (
            calibration.matrix()
            if calibration is not None
            and (len(calibration.points) == 4 or calibration.homography is not None)
            else None
        )
        tracks: dict[int, dict[str, Any]] = {}
        jerseys = JerseyGroups()
        camera = CameraRegistration() if calibration and calibration.compensate_camera else None
        camera_valid_frames = 0
        camera_failed_at_s = None
        ball_samples: list[dict[str, Any]] = []
        ball_frames = 0
        multiple_ball_frames = 0
        filtered_person_detections = 0
        field_filter_frames = 0
        frame_index = 0
        max_simultaneous = 0
        sample_stride = max(1, math.ceil(fps * 0.4))
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if pitch_model is not None and (
                frame_index == 0 or frame_index % max(1, round(fps)) == 0
            ):
                pitch_result = next(
                    iter(pitch_model.predict(frame, verbose=False, device=device))
                )
                detected_pitch = calibration_from_keypoint_result(pitch_result, width, height)
                if detected_pitch is not None:
                    calibration = detected_pitch
                    transform = calibration.matrix()
            if frame_index == 0 and calibration is not None and transform is None:
                if len(calibration.points) != 4:
                    detected = visible_pitch_points(frame)
                    if detected is None:
                        raise ValueError(
                            "Meydança küncləri avtomatik tapılmadı. "
                            "Görünən otun dörd küncünü seçin."
                        )
                    calibration = calibration.model_copy(update={"points": detected})
                calibration = adjust_visible_length(calibration)
                transform = calibration.matrix()
            if frame_index >= fps * max_seconds + 1:
                raise ValueError(f"Use a clip no longer than {max_seconds} seconds.")
            # Keep native time spacing; process every frame rather than misleading the tracker.
            results = model.track(
                frame,
                persist=True,
                tracker="botsort.yaml",
                classes=person_classes + referee_classes + ball_classes,
                conf=0.25,
                imgsz=image_size,
                verbose=False,
                device=device,
            )
            result = next(iter(results))
            boxes = result.boxes
            visible = 0
            radar: list[tuple[float, float, int | None]] = []
            detections: list[tuple[list[float], int, float, int]] = []
            if boxes is not None and boxes.id is not None:
                # Ultralytics exposes this conversion without a complete type annotation.
                boxes = boxes.cpu().numpy()  # type: ignore[no-untyped-call]
                assert boxes.id is not None
                detections = [
                    (box, int(identity), float(confidence), int(kind))
                    for box, identity, confidence, kind in zip(
                        boxes.xyxy.tolist(),
                        boxes.id.tolist(),
                        boxes.conf.tolist(),
                        boxes.cls.tolist(),
                        strict=True,
                    )
                ]
            # All following appearance/registration measurements use the unannotated frame.
            region = (
                field_region(frame) if os.environ.get("DEMO_FIELD_FILTER", "1") == "1" else None
            )
            field_filter_frames += int(region is not None)
            if camera:
                valid = camera.update(frame, [box for box, _, _, _ in detections])
                camera_valid_frames += int(valid)
                if not valid and camera_failed_at_s is None:
                    camera_failed_at_s = round(frame_index / fps, 3)
            people = [item for item in detections if item[3] in person_classes]
            referees = [item for item in detections if item[3] in referee_classes]
            features = (
                {
                    identity: shirt_feature(frame, box)
                    for box, identity, _, _ in people
                    if on_field(box, region)
                }
                if frame_index % 3 == 0
                else {}
            )
            for identity, feature in features.items():
                jerseys.observe(identity, feature)
            if jerseys.centers is None and frame_index >= fps * 1.2 and frame_index % 10 == 0:
                jerseys.fit()
            balls = [item for item in detections if item[3] in ball_classes]
            if balls:
                ball_frames += 1
                multiple_ball_frames += int(len(balls) > 1)
                box, identity, confidence, _ = max(balls, key=lambda item: item[2])
                bx, by = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                ball_samples.append(
                    {
                        "t": round(frame_index / fps, 3),
                        "x": round(bx / width, 6),
                        "y": round(by / height, 6),
                        "confidence": round(confidence, 3),
                        "track_id": identity,
                        "candidate_count": len(balls),
                    }
                )
                cv2.circle(frame, (int(bx), int(by)), 10, (60, 230, 255), 2)
                cv2.putText(
                    frame,
                    "BALL",
                    (int(bx) + 12, int(by)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (60, 230, 255),
                    2,
                )
            for box, identity, _confidence, _kind in referees:
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (185, 185, 185), 2)
                cv2.putText(
                    frame,
                    f"REF {identity}",
                    (int(x1), max(18, int(y1) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (185, 185, 185),
                    2,
                )
            for box, identity, confidence, kind in people:
                if not on_field(box, region):
                    filtered_person_detections += 1
                    continue
                x1, y1, x2, y2 = box
                x, y = (x1 + x2) / (2 * width), min(1.0, y2 / height)
                reference = camera.reference_point(x, y) if camera else (x, y)
                ground = (
                    ground_point(*reference, calibration, transform)
                    if reference is not None
                    else None
                )
                # Calibrated polygon also excludes spectators outside the pitch.
                if calibration and reference is not None and ground is None:
                    continue
                visible += 1
                role = str(model.names.get(kind, "player")).lower()
                if role not in {"player", "goalkeeper"}:
                    role = "player"
                record = tracks.setdefault(
                    identity, {"frames": 0, "samples": [], "segment": 0, "role": role}
                )
                gap = record.get("last_frame", frame_index - 1) != frame_index - 1
                if gap:
                    record["segment"] += 1
                record["last_frame"] = frame_index
                record["frames"] += 1
                samples = record["samples"]
                if not samples or gap or frame_index - record["last_sample_frame"] >= sample_stride:
                    samples.append(
                        {
                            "t": round(frame_index / fps, 6),
                            "x": round(x, 6),
                            "y": round(y, 6),
                            "confidence": round(confidence, 4),
                            "ground": [round(v, 6) for v in ground] if ground else None,
                            "segment": record["segment"],
                        }
                    )
                    record["last_sample_frame"] = frame_index
                team = jerseys.team(identity)
                color = TEAM_COLORS[team]
                if calibration and ground:
                    radar.append(
                        (ground[0] / calibration.length_m, ground[1] / calibration.width_m, team)
                    )
                elif calibration is None:
                    radar.append((x, y, team))
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(
                    frame,
                    f"{'GK' if role == 'goalkeeper' else 'P'} {identity} "
                    f"G{team or '?'}  {confidence:.2f}",
                    (int(x1), max(18, int(y1) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    color,
                    2,
                )
                cv2.circle(frame, (int(x * width), int(y * height)), 4, color, -1)
            _draw_radar(frame, radar, calibration is not None, camera is None or camera.valid)
            max_simultaneous = max(max_simultaneous, visible)
            cv2.putText(
                frame,
                f"{frame_index / fps:.1f}s | Visible tracks: {visible}",
                (16, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )
            writer.write(cv2.resize(frame, output_size))
            frame_index += 1
            if frame_index % max(1, round(fps)) == 0:
                progress(
                    min(94, int(frame_index / max(total_frames, frame_index) * 94)),
                    f"{frame_index / fps:.1f} saniyə analiz edilib",
                )
        if frame_index == 0:
            raise ValueError("Video contains no decodable frames.")
        if jerseys.centers is None:
            jerseys.fit()
        if total_frames > 0 and frame_index < total_frames * 0.98:
            raise ValueError("Video decoding ended early. Re-encode or upload another clip.")
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    progress(96, "Analiz videosu və hesabat hazırlanır")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(raw_video),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(directory / "annotated.mp4"),
        ],
        check=True,
        capture_output=True,
        timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    raw_video.unlink(missing_ok=True)
    rows = [
        summarize_track(identity, record["samples"], record["frames"], fps, calibration is not None)
        for identity, record in sorted(tracks.items())
    ]
    for row in rows:
        row["last_seen_s"] = round(tracks[row["track_id"]]["last_frame"] / fps, 3)
        row["team_group"] = jerseys.team(row["track_id"])
        row["role"] = tracks[row["track_id"]].get("role", "player")
    rows.sort(key=lambda row: (-row["visible_seconds"], row["track_id"]))
    for group in (None, 1, 2):
        selected = rows if group is None else [row for row in rows if row["team_group"] == group]
        name = "heatmap.png" if group is None else f"heatmap-group-{group}.png"
        picture = heatmap(
            selected,
            calibration.length_m if calibration else None,
            calibration.width_m if calibration else None,
        )
        if not cv2.imwrite(str(directory / name), picture):
            raise ValueError("Heatmap could not be saved.")
    report = {
        "schema_version": 2,
        "model": Path(weights).name,
        "pitch_model": PITCH_NAME if pitch_model is not None else None,
        "tracker": "BoT-SORT",
        "duration_s": round(frame_index / fps, 3),
        "fps": fps,
        "frame_width": width,
        "frame_height": height,
        "processed_frames": frame_index,
        "track_count": len(rows),
        "max_simultaneous_tracks": max_simultaneous,
        "calibration": calibration.model_dump() if calibration else None,
        "elapsed_s": round(time.monotonic() - started, 2),
        "tracks": rows,
        "jersey_groups": jerseys.summary(),
        "team_track_counts": {
            str(group): sum(row["team_group"] == group for row in rows) for group in (1, 2, None)
        },
        "field_filter": {
            "method": "largest grass region convex hull",
            "active_frames": field_filter_frames,
            "rejected_person_detections": filtered_person_detections,
        },
        "ball": {
            "detected_frames": ball_frames,
            "observed_seconds": round(ball_frames / fps, 2),
            "coverage_percent": round(ball_frames / frame_index * 100, 2),
            "multiple_candidate_frames": multiple_ball_frames,
            "samples": ball_samples,
            "possession": None,
            "passes": None,
            "goals": None,
        },
        "camera_registration": {
            "enabled": camera is not None,
            "valid_frames": camera_valid_frames if camera else None,
            "failed_at_s": camera_failed_at_s,
            "failure_reason": camera.reason if camera else None,
            "method": "background optical flow + RANSAC homography" if camera else None,
        },
        "limitations": [
            "Person detections can include referees and spectators; IDs are not player identities.",
            "IDs may switch or fragment after occlusions or cuts. Track count is not player count.",
            "Jersey groups estimate colour, not verified team identity. Similar kits may fail.",
            "Ball detection coverage is not possession. No goals, passes or ratings are inferred.",
            "Metrics require accurate user calibration; camera propagation is experimental.",
            "Camera failure stops metric output; accumulated drift remains possible.",
            "Distance covers observed segments only; gaps are not filled. Box jitter remains.",
            "Timestamps use nominal FPS. Convert variable-frame-rate videos to constant FPS first.",
        ],
    }
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    columns = [key for key in rows[0] if key != "samples"] if rows else ["track_id"]
    with (directory / "tracks.csv").open("w", encoding="utf-8-sig", newline="") as file:
        csv_writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        csv_writer.writeheader()
        csv_writer.writerows(rows)
    return report


def _draw_radar(
    frame: Any,
    points: list[tuple[float, float, int | None]],
    calibrated: bool,
    registration_valid: bool,
) -> None:
    height, width = frame.shape[:2]
    radar_width, radar_height = min(340, width // 3), min(190, height // 3)
    if radar_width < 120 or radar_height < 80:
        return
    left, top = width - radar_width - 15, 45
    cv2.rectangle(frame, (left, top), (left + radar_width, top + radar_height), (25, 40, 28), -1)
    label = "PITCH ESTIMATE" if calibrated else "IMAGE POSITIONS"
    if not registration_valid:
        label = "CALIBRATION LOST"
    cv2.putText(
        frame, label, (left + 8, top + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1
    )
    if calibrated:
        cv2.rectangle(
            frame,
            (left + 6, top + 30),
            (left + radar_width - 6, top + radar_height - 6),
            (150, 175, 150),
            1,
        )
    for x, y, team in points:
        cv2.circle(
            frame,
            (left + 6 + int(x * (radar_width - 12)), top + 30 + int(y * (radar_height - 36))),
            4,
            TEAM_COLORS[team],
            -1,
        )

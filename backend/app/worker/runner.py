from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.processing import ProcessingStage, ProcessingStatus
from app.schemas.processing import WorkerAssignmentContext
from app.worker.analyzer import analyze_video
from app.worker.api import WorkerApi, WorkerApiError, worker_settings
from app.worker.mapping import map_tracks_to_assignments

logger = logging.getLogger(__name__)


def run_forever(poll_seconds: float = 3.0) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    base_url, token, video_root = worker_settings()
    api = WorkerApi(base_url, token)
    logger.info("local_video_worker_started")
    while True:
        try:
            process_available_jobs(api, Path(video_root))
        except Exception:
            logger.exception("local_video_worker_loop_failed")
        time.sleep(poll_seconds)


def process_available_jobs(api: WorkerApi, video_root: Path) -> None:
    for summary in api.list_queued():
        job_id = uuid.UUID(summary["id"])
        process_job(api, video_root, job_id)


def process_job(api: WorkerApi, video_root: Path, job_id: uuid.UUID) -> None:
    context = api.get_context(job_id)
    if context["status"] != ProcessingStatus.QUEUED.value:
        return
    assignments = [WorkerAssignmentContext.model_validate(item) for item in context["assignments"]]
    video_path = (video_root / context["source_reference"]).resolve()
    try:
        _report(api, job_id, ProcessingStage.VALIDATING, 8)
        if not str(video_path).startswith(str(video_root.resolve())) or not video_path.is_file():
            _fail(api, job_id, "INVALID_VIDEO")
            return
        _report(api, job_id, ProcessingStage.PREPROCESSING, 18)
        _report(api, job_id, ProcessingStage.DETECTING_PLAYERS, 32)
        tracks = analyze_video(video_path)
        if not tracks:
            _fail(api, job_id, "NO_MOTION_DETECTED")
            return
        if not assignments:
            refreshed = api.ensure_detected_roster(job_id, min(22, len(tracks)))
            assignments = [
                WorkerAssignmentContext.model_validate(item) for item in refreshed["assignments"]
            ]
        if not assignments:
            _fail(api, job_id, "PLAYER_MAPPING_FAILED")
            return
        _report(api, job_id, ProcessingStage.TRACKING_PLAYERS, 55)
        mapped = map_tracks_to_assignments(tracks, assignments)
        if not mapped:
            _fail(api, job_id, "PLAYER_MAPPING_FAILED")
            return
        _report(api, job_id, ProcessingStage.CALIBRATING_FIELD, 68)
        _report(api, job_id, ProcessingStage.CALCULATING_METRICS, 80)
        _report(api, job_id, ProcessingStage.PERSISTING_RESULTS, 90)
        for index, (assignment, track) in enumerate(mapped):
            payload = _ingest_payload(assignment, track, complete=index == len(mapped) - 1)
            api.ingest(
                job_id,
                payload,
                idempotency_key=f"{job_id}:{assignment.player_id}",
            )
        logger.info("local_video_job_completed", extra={"job_id": str(job_id)})
    except ValueError as error:
        code = "INVALID_VIDEO" if str(error) == "VIDEO_UNREADABLE" else "PROCESSING_FAILED"
        _fail(api, job_id, code)
    except WorkerApiError as error:
        logger.exception(
            "local_video_job_api_failed",
            extra={"job_id": str(job_id), "status": error.status, "body": error.body[:500]},
        )
        try:
            _fail(api, job_id, "PROCESSING_FAILED")
        except WorkerApiError:
            return


def _ingest_payload(
    assignment: WorkerAssignmentContext,
    track: Any,
    *,
    complete: bool,
) -> dict[str, Any]:
    return {
        "player_id": str(assignment.player_id),
        "team_id": str(assignment.team_id),
        "provider_track_id": track.track_id,
        "metrics": {
            "rating": track.rating,
            "distance_m": track.distance_m,
            "avg_speed_kmh": track.avg_speed_kmh,
            "max_speed_kmh": track.max_speed_kmh,
            "sprint_count": track.sprint_count,
            "active_seconds": track.active_seconds,
            "activity_count": track.activity_count,
            "peak_speed_at_ms": track.peak_speed_at_ms,
        },
        "positions": [
            {"timestamp_ms": sample.timestamp_ms, "x": sample.x, "y": sample.y}
            for sample in track.positions
        ],
        "intensity": [
            {"from_minute": start, "to_minute": end, "intensity": value}
            for start, end, value in track.intensity
        ],
        "events": [
            {
                "event_type": event_type,
                "timestamp_ms": stamp,
                "speed_kmh": speed,
                "title": title,
            }
            for event_type, stamp, speed, title in track.events
        ],
        "calibration": {
            "version": "local-motion-v1",
            "source_frame_width": track.frame_width,
            "source_frame_height": track.frame_height,
            "pitch_length_m": 105,
            "pitch_width_m": 68,
            "transform_metadata": {"method": "normalized-frame"},
        },
        "complete_job": complete,
    }


def _report(api: WorkerApi, job_id: uuid.UUID, stage: ProcessingStage, progress: int) -> None:
    status = (
        ProcessingStatus.PROCESSING
        if stage != ProcessingStage.COMPLETED
        else ProcessingStatus.COMPLETED
    )
    api.update_state(
        job_id,
        {
            "status": status.value,
            "stage": stage.value,
            "progress": progress,
            "provider_run_id": "local-motion-worker",
        },
    )


def _fail(api: WorkerApi, job_id: uuid.UUID, error_code: str) -> None:
    logger.warning(
        "local_video_job_failed",
        extra={"job_id": str(job_id), "error_code": error_code},
    )
    try:
        api.update_state(
            job_id,
            {
                "status": ProcessingStatus.FAILED.value,
                "stage": ProcessingStage.DETECTING_PLAYERS.value,
                "progress": 20,
                "error_code": error_code,
                "error_message": error_code,
                "provider_run_id": "local-motion-worker",
            },
        )
    except WorkerApiError as error:
        if error.status == 409:
            return
        raise

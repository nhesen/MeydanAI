import math
import uuid
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import PlayerMatchAnalytics, ProcessingJob, ProcessingTrackMapping
from app.schemas.analysis import AnalysisQuality, ReviewStatus


def latest_analysis_job(session: Session, match_id: uuid.UUID) -> ProcessingJob | None:
    return session.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.match_id == match_id, ProcessingJob.status == "completed")
        .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id)
        .limit(1)
    )


def review_metadata(job: ProcessingJob | None) -> dict[str, Any]:
    value = (job.calibration_metadata or {}).get("reviews") if job else None
    return dict(value) if isinstance(value, dict) else {}


def event_review_status(reviews: dict[str, Any], event_id: uuid.UUID) -> ReviewStatus:
    event = reviews.get("events", {}).get(str(event_id), {})
    status = event.get("status", "pending")
    if status == "confirmed":
        return "confirmed"
    if status == "rejected":
        return "rejected"
    return "pending"


def rejected_highlight_ids(session: Session, match_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    return [
        key
        for key, status in highlight_review_states(session, match_id).items()
        if status == "rejected"
    ]


def highlight_review_states(
    session: Session, match_id: uuid.UUID | None = None
) -> dict[uuid.UUID, ReviewStatus]:
    query = select(ProcessingJob)
    if match_id is not None:
        query = query.where(ProcessingJob.match_id == match_id)
    states: dict[uuid.UUID, ReviewStatus] = {}
    for job in session.scalars(query.order_by(ProcessingJob.created_at)):
        for review in review_metadata(job).get("events", {}).values():
            if review.get("status") not in {"confirmed", "rejected"}:
                continue
            for raw in review.get("highlight_ids", []):
                try:
                    states[uuid.UUID(raw)] = review["status"]
                except (ValueError, TypeError, AttributeError):
                    continue
    return states


def analysis_quality(
    session: Session,
    match_id: uuid.UUID,
    player_id: uuid.UUID | None = None,
    *,
    job: ProcessingJob | None = None,
) -> AnalysisQuality:
    job = job or latest_analysis_job(session, match_id)
    if job is None:
        return AnalysisQuality()
    metadata = job.calibration_metadata or {}
    query = select(ProcessingTrackMapping).where(ProcessingTrackMapping.job_id == job.id)
    if player_id is not None:
        query = query.where(ProcessingTrackMapping.player_id == player_id)
    mappings = list(session.scalars(query))
    reviews = review_metadata(job).get("identities", {})
    identity: Literal["estimated", "confirmed", "unavailable"] = "unavailable"
    if mappings:
        identity = (
            "confirmed"
            if all(
                reviews.get(str(mapping.id), {}).get("status") == "confirmed"
                for mapping in mappings
            )
            else "estimated"
        )
    all_results = metadata.get("track_results", {})
    all_results = all_results if isinstance(all_results, dict) else {}
    selected = list(all_results.values())
    if player_id is not None and all_results:
        selected = [
            all_results[mapping.provider_track_id]
            for mapping in mappings
            if mapping.provider_track_id in all_results
        ]
        if not selected and f"player:{player_id}" in all_results:
            selected = [all_results[f"player:{player_id}"]]
    if not all_results:
        result = metadata.get("result", metadata)
        selected = [{"calibration": result, "physical_metrics_available": False}]
    calibrations = [entry.get("calibration", {}) for entry in selected]
    transforms = [value.get("transform_metadata", {}) for value in calibrations]
    calibrated = any(transform.get("calibrated") is True for transform in transforms)
    physical_available = any(entry.get("physical_metrics_available") is True for entry in selected)
    if not all_results and player_id is not None:
        analytics = session.scalar(
            select(PlayerMatchAnalytics).where(
                PlayerMatchAnalytics.match_id == match_id,
                PlayerMatchAnalytics.player_id == player_id,
            )
        )
        physical_available = (
            calibrated
            and bool(mappings)
            and analytics is not None
            and analytics.distance_m is not None
        )

    def numeric(value: Any) -> float | None:
        return float(value) if isinstance(value, (float, int)) and math.isfinite(value) else None

    def dimension(key: str) -> float | None:
        return next(
            (
                numeric(value.get(key))
                for value in calibrations
                if numeric(value.get(key)) is not None
            ),
            None,
        )

    coverage = [
        number
        for value in transforms
        if (number := numeric(value.get("calibration_coverage"))) is not None
    ]
    measured = [
        number
        for value in transforms
        if (number := numeric(value.get("measured_seconds"))) is not None
    ]
    methods = {str(transform.get("method", "unknown")) for transform in transforms}

    return AnalysisQuality(
        job_id=job.id,
        calibrated=calibrated,
        source=next(iter(methods)) if len(methods) == 1 else "mixed" if methods else "unavailable",
        physical_metrics_available=physical_available,
        identity_mapping=identity,
        pitch_length_m=dimension("pitch_length_m"),
        pitch_width_m=dimension("pitch_width_m"),
        calibration_coverage=sum(coverage) / len(coverage) if coverage else None,
        measured_seconds=sum(measured) if measured else None,
        ball_observed_coverage=next(
            (
                numeric(value.get("ball_observed_coverage"))
                for value in transforms
                if numeric(value.get("ball_observed_coverage")) is not None
            ),
            None,
        ),
        sprint_threshold_kmh=next(
            (
                numeric(value.get("sprint_threshold_kmh"))
                for value in transforms
                if numeric(value.get("sprint_threshold_kmh")) is not None
            ),
            None,
        ),
        sprint_min_duration_s=next(
            (
                numeric(value.get("sprint_min_duration_s"))
                for value in transforms
                if numeric(value.get("sprint_min_duration_s")) is not None
            ),
            None,
        ),
    )

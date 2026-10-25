import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, delete, insert, select, update
from sqlalchemy.orm import Session

from app.core.analysis_metadata import (
    analysis_quality,
    event_review_status,
    latest_analysis_job,
    review_metadata,
)
from app.core.exceptions import DomainError
from app.models.domain import (
    Highlight,
    JerseyAssignment,
    Player,
    PlayerAnalyticsEvent,
    PlayerIntensityBucket,
    PlayerMatchAnalytics,
    PlayerPositionSample,
    ProcessingJob,
    ProcessingTrackMapping,
    User,
)
from app.repositories.processing import ProcessingRepository
from app.schemas.analysis import (
    AnalysisReviewResponse,
    EventReviewItem,
    EventReviewUpdate,
    IdentityReviewItem,
    IdentityReviewUpdate,
    TrackEvidence,
    UploadCalibrationConfig,
)
from app.services.audit import AuditService
from app.services.matches import MatchService, normalize_name

METRIC_FIELDS = (
    "status",
    "rating",
    "distance_m",
    "avg_speed_kmh",
    "max_speed_kmh",
    "sprint_count",
    "active_seconds",
    "activity_count",
    "peak_speed_at_ms",
)


class AnalysisReviewService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_review(
        self, match_id: uuid.UUID, token: str | None, user: User | None
    ) -> AnalysisReviewResponse:
        MatchService(self.session).get_organizer_match(match_id, token, user)
        job = latest_analysis_job(self.session, match_id)
        if job is None:
            return AnalysisReviewResponse(
                job_id=None,
                status=None,
                calibration_config=None,
                analysis_quality=analysis_quality(self.session, match_id),
                mappings=[],
                events=[],
            )
        metadata = job.calibration_metadata or {}
        reviews = review_metadata(job)
        evidence = metadata.get("track_evidence", {})
        evidence = evidence if isinstance(evidence, dict) else {}
        identities = reviews.get("identities", {})
        mappings = list(
            self.session.scalars(
                select(ProcessingTrackMapping)
                .where(ProcessingTrackMapping.job_id == job.id)
                .order_by(ProcessingTrackMapping.provider_track_id)
            )
        )
        items = []
        for mapping in mappings:
            player = self.session.get(Player, mapping.player_id) if mapping.player_id else None
            assignment = self.session.scalar(
                select(JerseyAssignment)
                .where(
                    JerseyAssignment.match_id == match_id,
                    JerseyAssignment.player_id == mapping.player_id,
                    JerseyAssignment.team_id == mapping.team_id,
                )
                .order_by(JerseyAssignment.created_at.desc())
                .limit(1)
            )
            raw_evidence = evidence.get(mapping.provider_track_id)
            items.append(
                IdentityReviewItem(
                    id=mapping.id,
                    provider_track_id=mapping.provider_track_id,
                    player_id=mapping.player_id,
                    team_id=mapping.team_id,
                    display_name=player.display_name if player else None,
                    jersey_number=assignment.jersey_number if assignment else None,
                    review_status="confirmed"
                    if identities.get(str(mapping.id), {}).get("status") == "confirmed"
                    else "estimated",
                    evidence=TrackEvidence.model_validate(raw_evidence) if raw_evidence else None,
                    can_rename=bool(player and self._can_rename(player)),
                )
            )
        events = []
        for event, analytics in self.session.execute(
            select(PlayerAnalyticsEvent, PlayerMatchAnalytics)
            .join(
                PlayerMatchAnalytics, PlayerAnalyticsEvent.analytics_id == PlayerMatchAnalytics.id
            )
            .where(PlayerMatchAnalytics.match_id == match_id)
            .order_by(PlayerAnalyticsEvent.timestamp_ms)
        ):
            highlight = self.session.scalar(
                select(Highlight)
                .where(
                    Highlight.match_id == match_id,
                    Highlight.player_id == analytics.player_id,
                    Highlight.timestamp_ms == event.timestamp_ms,
                    Highlight.title == f"AI: {event.title}"[:140],
                )
                .limit(1)
            )
            events.append(
                EventReviewItem(
                    id=event.id,
                    player_id=analytics.player_id,
                    team_id=analytics.team_id,
                    event_type=event.event_type,
                    timestamp_ms=event.timestamp_ms,
                    title=event.title,
                    review_status=event_review_status(reviews, event.id),
                    video_url=highlight.video_url if highlight else None,
                )
            )
        return AnalysisReviewResponse(
            job_id=job.id,
            status=job.status,
            calibration_config=UploadCalibrationConfig.model_validate(
                metadata.get("upload_config", {})
            ),
            analysis_quality=analysis_quality(self.session, match_id, job=job),
            mappings=items,
            events=events,
        )

    def review_event(
        self,
        match_id: uuid.UUID,
        event_id: uuid.UUID,
        payload: EventReviewUpdate,
        token: str | None,
        user: User | None,
    ) -> AnalysisReviewResponse:
        job = self._writable_job(match_id, token, user)
        row = self.session.execute(
            select(PlayerAnalyticsEvent, PlayerMatchAnalytics)
            .join(
                PlayerMatchAnalytics, PlayerAnalyticsEvent.analytics_id == PlayerMatchAnalytics.id
            )
            .where(PlayerAnalyticsEvent.id == event_id, PlayerMatchAnalytics.match_id == match_id)
        ).first()
        if row is None:
            raise self._error(
                404, "ANALYTICS_EVENT_NOT_FOUND", "The event does not belong to this match."
            )
        event, analytics = row
        highlights = list(
            self.session.scalars(
                select(Highlight.id).where(
                    Highlight.match_id == match_id,
                    Highlight.player_id == analytics.player_id,
                    Highlight.timestamp_ms == event.timestamp_ms,
                    Highlight.title == f"AI: {event.title}"[:140],
                )
            )
        )
        self._save_review(
            job,
            "events",
            str(event_id),
            {
                "status": payload.status,
                "highlight_ids": [str(value) for value in highlights],
                "reviewed_at": datetime.now(UTC).isoformat(),
                "actor_id": str(user.id) if user else None,
            },
        )
        AuditService(self.session).record(
            actor_user_id=user.id if user else None,
            action="analysis.event.review",
            entity_type="player_analytics_event",
            entity_id=str(event_id),
            metadata={"status": payload.status, "match_id": str(match_id)},
        )
        self.session.commit()
        return self.get_review(match_id, token, user)

    def review_identity(
        self,
        match_id: uuid.UUID,
        mapping_id: uuid.UUID,
        payload: IdentityReviewUpdate,
        token: str | None,
        user: User | None,
    ) -> AnalysisReviewResponse:
        job = self._writable_job(match_id, token, user)
        mapping = self.session.scalar(
            select(ProcessingTrackMapping)
            .where(ProcessingTrackMapping.id == mapping_id, ProcessingTrackMapping.job_id == job.id)
            .with_for_update()
        )
        if mapping is None or mapping.player_id is None or mapping.team_id is None:
            raise self._error(404, "TRACK_MAPPING_NOT_FOUND", "The track mapping is unavailable.")
        evidence = (job.calibration_metadata or {}).get("track_evidence", {})
        evidence = evidence if isinstance(evidence, dict) else {}
        if not evidence.get(mapping.provider_track_id, {}).get("image_url"):
            raise self._error(
                409,
                "IDENTITY_EVIDENCE_UNAVAILABLE",
                "Analyze the video again to generate a reference image before confirming identity.",
            )
        matches = MatchService(self.session)
        if not matches.repository.player_belongs_to_match_team(
            match_id, payload.team_id, payload.player_id
        ):
            raise self._error(
                422,
                "PLAYER_MAPPING_FAILED",
                "Choose a player assigned to the selected team in this match.",
            )
        old_player, old_team = mapping.player_id, mapping.team_id
        if payload.display_name is not None:
            player = self.session.get(Player, payload.player_id)
            if player is None or not self._can_rename(player):
                raise self._error(
                    422,
                    "PLAYER_NAME_PROTECTED",
                    "Only a temporary player without an account can be renamed here.",
                )
            cleaned_name = " ".join(payload.display_name.split())
            if len(cleaned_name) < 2:
                raise self._error(
                    422, "INVALID_PLAYER_NAME", "Enter at least two characters for the player name."
                )
            player.display_name = cleaned_name
            player.normalized_name = normalize_name(cleaned_name)
        if old_player != payload.player_id:
            self._remap_analytics(
                match_id, old_player, old_team, payload.player_id, payload.team_id
            )
            others = list(
                self.session.scalars(
                    select(ProcessingTrackMapping).where(
                        ProcessingTrackMapping.job_id == job.id,
                        ProcessingTrackMapping.player_id == payload.player_id,
                        ProcessingTrackMapping.id != mapping.id,
                    )
                )
            )
            for other in others:
                other.player_id, other.team_id = old_player, old_team
                self._save_review(job, "identities", str(other.id), {"status": "estimated"})
        mapping.player_id, mapping.team_id = payload.player_id, payload.team_id
        self._save_review(
            job,
            "identities",
            str(mapping_id),
            {
                "status": "confirmed",
                "reviewed_at": datetime.now(UTC).isoformat(),
                "actor_id": str(user.id) if user else None,
                "player_id": str(payload.player_id),
                "team_id": str(payload.team_id),
            },
        )
        AuditService(self.session).record(
            actor_user_id=user.id if user else None,
            action="analysis.identity.review",
            entity_type="processing_track_mapping",
            entity_id=str(mapping_id),
            metadata={
                "old_player_id": str(old_player),
                "player_id": str(payload.player_id),
                "match_id": str(match_id),
                "display_name": payload.display_name,
            },
        )
        self.session.commit()
        self.session.expire_all()
        return self.get_review(match_id, token, user)

    def _can_rename(self, player: Player) -> bool:
        return (
            player.is_temporary
            and self.session.scalar(select(User.id).where(User.player_id == player.id).limit(1))
            is None
        )

    def _remap_analytics(
        self,
        match_id: uuid.UUID,
        old_player: uuid.UUID,
        old_team: uuid.UUID,
        new_player: uuid.UUID,
        new_team: uuid.UUID,
    ) -> None:
        source = self.session.scalar(
            select(PlayerMatchAnalytics)
            .where(
                PlayerMatchAnalytics.match_id == match_id,
                PlayerMatchAnalytics.player_id == old_player,
            )
            .with_for_update()
        )
        target = self.session.scalar(
            select(PlayerMatchAnalytics)
            .where(
                PlayerMatchAnalytics.match_id == match_id,
                PlayerMatchAnalytics.player_id == new_player,
            )
            .with_for_update()
        )
        if source is None:
            raise self._error(409, "ANALYTICS_UNAVAILABLE", "The track has no analytics to remap.")
        if target is None:
            source.player_id, source.team_id = new_player, new_team
        else:
            for field in METRIC_FIELDS:
                left, right = getattr(source, field), getattr(target, field)
                setattr(source, field, right)
                setattr(target, field, left)
            source.team_id, target.team_id = old_team, new_team
            for model in (PlayerPositionSample, PlayerAnalyticsEvent):
                self.session.execute(
                    update(model)
                    .where(model.analytics_id.in_((source.id, target.id)))
                    .values(
                        analytics_id=case(
                            (model.analytics_id == source.id, target.id), else_=source.id
                        )
                    )
                    .execution_options(synchronize_session=False)
                )
            # Preserve bucket IDs without colliding with the unique interval constraint.
            buckets = list(
                self.session.scalars(
                    select(PlayerIntensityBucket).where(
                        PlayerIntensityBucket.analytics_id.in_((source.id, target.id))
                    )
                )
            )
            records = [
                {
                    "id": bucket.id,
                    "analytics_id": target.id if bucket.analytics_id == source.id else source.id,
                    "from_minute": bucket.from_minute,
                    "to_minute": bucket.to_minute,
                    "intensity": bucket.intensity,
                }
                for bucket in buckets
            ]
            self.session.execute(
                delete(PlayerIntensityBucket)
                .where(PlayerIntensityBucket.analytics_id.in_((source.id, target.id)))
                .execution_options(synchronize_session=False)
            )
            if records:
                self.session.execute(insert(PlayerIntensityBucket), records)
        self.session.execute(
            update(Highlight)
            .where(
                Highlight.match_id == match_id,
                Highlight.title.like("AI: %"),
                Highlight.player_id.in_((old_player, new_player)),
            )
            .values(
                player_id=case((Highlight.player_id == old_player, new_player), else_=old_player)
            )
            .execution_options(synchronize_session=False)
        )

    def _writable_job(
        self, match_id: uuid.UUID, token: str | None, user: User | None
    ) -> ProcessingJob:
        MatchService(self.session).get_organizer_match(match_id, token, user)
        repository = ProcessingRepository(self.session)
        repository.lock_match(match_id)
        if repository.get_active_job(match_id) is not None:
            raise self._error(
                409,
                "MATCH_PROCESSING_ACTIVE",
                "Wait for the current analysis before reviewing results.",
            )
        job = latest_analysis_job(self.session, match_id)
        if job is None:
            raise self._error(
                409, "ANALYSIS_NOT_REVIEWABLE", "Complete an analysis before reviewing its results."
            )
        return job

    @staticmethod
    def _save_review(job: ProcessingJob, kind: str, key: str, value: dict[str, Any]) -> None:
        metadata = dict(job.calibration_metadata or {})
        reviews = review_metadata(job)
        reviews[kind] = {**reviews.get(kind, {}), key: value}
        metadata["reviews"] = reviews
        job.calibration_metadata = metadata

    @staticmethod
    def _error(status: int, code: str, detail: str) -> DomainError:
        return DomainError(
            status=status, title="Analysis review unavailable", detail=detail, error_code=code
        )

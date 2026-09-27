import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.processing import ProcessingStage, ProcessingStatus
from app.models.domain import (
    PlayerAnalyticsEvent,
    PlayerIntensityBucket,
    PlayerMatchAnalytics,
    PlayerPositionSample,
    ProcessingIngestionBatch,
    ProcessingTrackMapping,
)
from app.repositories.matches import MatchRepository
from app.repositories.processing import ProcessingRepository
from app.schemas.ingestion import AnalyticsIngestionResponse, PlayerAnalyticsIngest

logger = logging.getLogger(__name__)


class AnalyticsIngestionService:
    def __init__(
        self,
        session: Session,
        *,
        max_position_samples: int,
    ) -> None:
        self.session = session
        self.max_position_samples = max_position_samples
        self.processing_repository = ProcessingRepository(session)
        self.match_repository = MatchRepository(session)

    def ingest(
        self,
        job_id: uuid.UUID,
        idempotency_key: str,
        payload: PlayerAnalyticsIngest,
    ) -> AnalyticsIngestionResponse:
        if len(payload.positions) > self.max_position_samples:
            raise DomainError(
                status=413,
                title="Analytics batch is too large",
                detail="Split position samples into a smaller player result batch.",
                error_code="ANALYTICS_BATCH_TOO_LARGE",
            )
        payload_hash = self._payload_hash(payload)
        existing_batch = self.processing_repository.get_ingestion_batch(
            job_id,
            idempotency_key,
        )
        if existing_batch is not None:
            existing_job = self.processing_repository.get_job(job_id)
            if existing_job is None:
                raise self._not_found(
                    "Processing job was not found.",
                    "PROCESSING_JOB_NOT_FOUND",
                )
            return self._idempotent_response(
                existing_batch,
                payload_hash,
                ProcessingStatus(existing_job.status),
            )

        job = self.processing_repository.get_job(job_id, for_update=True)
        if job is None:
            raise self._not_found(
                "Processing job was not found.",
                "PROCESSING_JOB_NOT_FOUND",
            )
        if ProcessingStatus(job.status) != ProcessingStatus.PROCESSING:
            raise self._conflict(
                "Analytics can only be ingested for a processing job.",
                "JOB_NOT_ACCEPTING_ANALYTICS",
            )
        self._validate_player_mapping(
            job.match_id,
            payload.player_id,
            payload.team_id,
        )
        for mapping in payload.track_mappings:
            if mapping.mapping_status == "mapped":
                assert mapping.player_id is not None
                assert mapping.team_id is not None
                self._validate_player_mapping(
                    job.match_id,
                    mapping.player_id,
                    mapping.team_id,
                )

        try:
            analytics = self.match_repository.get_player_analytics(
                job.match_id,
                payload.player_id,
            )
            if analytics is None:
                analytics = PlayerMatchAnalytics(
                    match_id=job.match_id,
                    player_id=payload.player_id,
                    team_id=payload.team_id,
                    status="available",
                )
                self.session.add(analytics)
                self.session.flush()
            else:
                analytics.position_samples.clear()
                analytics.intensity_buckets.clear()
                analytics.events.clear()
                self.session.flush()

            analytics.team_id = payload.team_id
            analytics.status = "available"
            metrics = payload.metrics
            analytics.rating = metrics.rating
            analytics.distance_m = metrics.distance_m
            analytics.avg_speed_kmh = metrics.avg_speed_kmh
            analytics.max_speed_kmh = metrics.max_speed_kmh
            analytics.sprint_count = metrics.sprint_count
            analytics.active_seconds = metrics.active_seconds
            analytics.activity_count = metrics.activity_count
            analytics.peak_speed_at_ms = metrics.peak_speed_at_ms
            analytics.position_samples = [
                PlayerPositionSample(
                    timestamp_ms=sample.timestamp_ms,
                    x=sample.x,
                    y=sample.y,
                )
                for sample in payload.positions
            ]
            analytics.intensity_buckets = [
                PlayerIntensityBucket(
                    from_minute=bucket.from_minute,
                    to_minute=bucket.to_minute,
                    intensity=bucket.intensity,
                )
                for bucket in payload.intensity
            ]
            analytics.events = [
                PlayerAnalyticsEvent(
                    event_type=event.event_type,
                    timestamp_ms=event.timestamp_ms,
                    speed_kmh=event.speed_kmh,
                    title=event.title,
                )
                for event in payload.events
            ]

            if payload.provider_track_id is not None:
                self._upsert_track_mapping(
                    job_id=job.id,
                    provider_track_id=payload.provider_track_id,
                    mapping_status="mapped",
                    player_id=payload.player_id,
                    team_id=payload.team_id,
                    observed_jersey=None,
                )
            for mapping in payload.track_mappings:
                self._upsert_track_mapping(
                    job_id=job.id,
                    provider_track_id=mapping.provider_track_id,
                    mapping_status=mapping.mapping_status,
                    player_id=mapping.player_id,
                    team_id=mapping.team_id,
                    observed_jersey=mapping.observed_jersey,
                )

            if payload.calibration is not None:
                job.calibration_metadata = payload.calibration.model_dump(mode="json")

            batch = ProcessingIngestionBatch(
                job_id=job.id,
                player_id=payload.player_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                position_count=len(payload.positions),
                intensity_bucket_count=len(payload.intensity),
                event_count=len(payload.events),
            )
            self.session.add(batch)
            if payload.complete_job:
                job.status = ProcessingStatus.COMPLETED.value
                job.stage = ProcessingStage.COMPLETED.value
                job.progress = 100
                job.completed_at = datetime.now(UTC)
            self.session.commit()
        except IntegrityError as exception:
            self.session.rollback()
            raced_batch = self.processing_repository.get_ingestion_batch(
                job_id,
                idempotency_key,
            )
            if raced_batch is not None:
                raced_job = self.processing_repository.get_job(job_id)
                if raced_job is not None:
                    return self._idempotent_response(
                        raced_batch,
                        payload_hash,
                        ProcessingStatus(raced_job.status),
                    )
            raise self._conflict(
                "The analytics batch conflicts with persisted data.",
                "ANALYTICS_INGESTION_CONFLICT",
            ) from exception
        except SQLAlchemyError as exception:
            self.session.rollback()
            logger.exception(
                "analytics_ingestion_persistence_failed",
                extra={"job_id": str(job_id), "player_id": str(payload.player_id)},
            )
            raise DomainError(
                status=500,
                title="Analytics persistence failed",
                detail="The analytics result could not be saved.",
                error_code="PERSISTENCE_FAILED",
            ) from exception

        logger.info(
            "analytics_ingestion_completed",
            extra={
                "job_id": str(job.id),
                "match_id": str(job.match_id),
                "player_id": str(payload.player_id),
                "status": job.status,
                "stage": job.stage,
            },
        )
        return AnalyticsIngestionResponse(
            batch_id=batch.id,
            duplicate=False,
            player_id=payload.player_id,
            position_count=batch.position_count,
            intensity_bucket_count=batch.intensity_bucket_count,
            event_count=batch.event_count,
            job_status=ProcessingStatus(job.status),
        )

    def _validate_player_mapping(
        self,
        match_id: uuid.UUID,
        player_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> None:
        if not self.match_repository.player_belongs_to_match_team(
            match_id,
            team_id,
            player_id,
        ):
            raise self._not_found(
                "The player and team mapping does not belong to this match.",
                "PLAYER_MAPPING_FAILED",
            )

    def _upsert_track_mapping(
        self,
        *,
        job_id: uuid.UUID,
        provider_track_id: str,
        mapping_status: str,
        player_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
        observed_jersey: int | None,
    ) -> None:
        mapping = self.processing_repository.get_track_mapping(
            job_id,
            provider_track_id,
        )
        if mapping is None:
            mapping = ProcessingTrackMapping(
                job_id=job_id,
                provider_track_id=provider_track_id,
                mapping_status=mapping_status,
            )
            self.session.add(mapping)
        mapping.mapping_status = mapping_status
        mapping.player_id = player_id
        mapping.team_id = team_id
        mapping.observed_jersey = observed_jersey

    @staticmethod
    def _payload_hash(payload: PlayerAnalyticsIngest) -> str:
        serialized = json.dumps(
            payload.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _idempotent_response(
        batch: ProcessingIngestionBatch,
        payload_hash: str,
        job_status: ProcessingStatus,
    ) -> AnalyticsIngestionResponse:
        if batch.payload_hash != payload_hash:
            raise AnalyticsIngestionService._conflict(
                "The idempotency key was already used for a different payload.",
                "IDEMPOTENCY_KEY_REUSED",
            )
        return AnalyticsIngestionResponse(
            batch_id=batch.id,
            duplicate=True,
            player_id=batch.player_id,
            position_count=batch.position_count,
            intensity_bucket_count=batch.intensity_bucket_count,
            event_count=batch.event_count,
            job_status=job_status,
        )

    @staticmethod
    def _not_found(detail: str, code: str) -> DomainError:
        return DomainError(
            status=404,
            title="Analytics mapping not found",
            detail=detail,
            error_code=code,
        )

    @staticmethod
    def _conflict(detail: str, code: str) -> DomainError:
        return DomainError(
            status=409,
            title="Analytics ingestion conflict",
            detail=detail,
            error_code=code,
        )

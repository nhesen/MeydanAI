from enum import StrEnum


class ProcessingStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStage(StrEnum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    PREPROCESSING = "preprocessing"
    DETECTING_PLAYERS = "detecting_players"
    TRACKING_PLAYERS = "tracking_players"
    CALIBRATING_FIELD = "calibrating_field"
    CALCULATING_METRICS = "calculating_metrics"
    PERSISTING_RESULTS = "persisting_results"
    COMPLETED = "completed"


class ProcessingSourceType(StrEnum):
    UPLOADED_VIDEO = "uploaded_video"


ALLOWED_PROCESSING_TRANSITIONS: dict[ProcessingStatus, frozenset[ProcessingStatus]] = {
    ProcessingStatus.QUEUED: frozenset({ProcessingStatus.PROCESSING, ProcessingStatus.CANCELLED}),
    ProcessingStatus.PROCESSING: frozenset(
        {
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
            ProcessingStatus.CANCELLED,
        }
    ),
    ProcessingStatus.COMPLETED: frozenset(),
    ProcessingStatus.FAILED: frozenset(),
    ProcessingStatus.CANCELLED: frozenset(),
}


def can_transition(current: ProcessingStatus, target: ProcessingStatus) -> bool:
    return target in ALLOWED_PROCESSING_TRANSITIONS[current]

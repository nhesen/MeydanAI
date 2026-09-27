import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.domain import AuditLog

logger = logging.getLogger(__name__)

SENSITIVE_METADATA_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "organizer_token",
        "join_token",
        "authorization",
        "cookie",
    }
)


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None,
        commit: bool = False,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                event_metadata=self._safe_metadata(metadata),
            )
        )
        if commit:
            self.session.commit()
        logger.info(
            "audit_recorded",
            extra={
                "user_id": str(actor_user_id) if actor_user_id else None,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
        )

    @staticmethod
    def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, object] | None:
        if not metadata:
            return None
        return {
            key: value
            for key, value in metadata.items()
            if key.casefold() not in SENSITIVE_METADATA_KEYS
        }

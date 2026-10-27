from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import ProcessingJob

_RECORDING_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,180}\.mp4")


def resolve_recording(root: Path, reference: str) -> Path | None:
    if reference != Path(reference).name or ".." in reference:
        return None
    if _RECORDING_NAME.fullmatch(reference) is None:
        return None
    base = root.resolve()
    path = (base / reference).resolve()
    if path.parent != base or not path.is_file():
        return None
    return path


def match_recording(session: Session, match_id: uuid.UUID, root: Path) -> Path | None:
    references = session.scalars(
        select(ProcessingJob.source_reference)
        .where(ProcessingJob.match_id == match_id)
        .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
    )
    for reference in references:
        path = resolve_recording(root, reference)
        if path is not None:
            return path
    return None

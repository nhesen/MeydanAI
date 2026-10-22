from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str


class CorrectionRequest(BaseModel):
    team: str | None = None
    jersey: int | None = Field(default=None, ge=0, le=99)
    name: str | None = None
    role: str | None = None

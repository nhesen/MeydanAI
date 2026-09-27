from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ApiResponse[T](BaseModel):
    data: T
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

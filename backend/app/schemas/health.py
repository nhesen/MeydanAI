from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: Literal["UP"]
    service: str

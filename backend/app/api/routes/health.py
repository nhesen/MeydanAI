from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.health import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse[HealthStatus])
def health() -> ApiResponse[HealthStatus]:
    return ApiResponse(data=HealthStatus(status="UP", service="meydanai-api"))

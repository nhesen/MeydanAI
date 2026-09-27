from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.internal_processing import router as internal_processing_router
from app.api.routes.join import router as join_router
from app.api.routes.matches import router as matches_router
from app.api.routes.processing_jobs import router as processing_jobs_router
from app.api.routes.public_matches import router as public_matches_router
from app.api.routes.public_platform import router as public_platform_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(matches_router)
api_router.include_router(join_router)
api_router.include_router(public_matches_router)
api_router.include_router(processing_jobs_router)
api_router.include_router(internal_processing_router)
api_router.include_router(public_platform_router)

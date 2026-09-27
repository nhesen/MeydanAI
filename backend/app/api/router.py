from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.join import router as join_router
from app.api.routes.matches import router as matches_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(matches_router)
api_router.include_router(join_router)

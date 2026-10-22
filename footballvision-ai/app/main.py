from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import load_config


def create_app() -> FastAPI:
    load_config()
    application = FastAPI(title="FootballVision AI", version="1.0.0")
    application.include_router(router)
    return application


app = create_app()

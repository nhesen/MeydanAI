"""Run with: python -m uvicorn app.demo.main:app --host 127.0.0.1 --port 8010."""

# Azerbaijani UI messages intentionally contain the dotless letter U+0131.
# ruff: noqa: RUF001

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.demo.analyzer import analyze
from app.demo.metrics import Calibration

logger = logging.getLogger(__name__)
MAX_BYTES = 500 * 1024 * 1024


def create_app(root: Path | None = None) -> FastAPI:
    storage = (root or Path(os.environ.get("DEMO_STORAGE_PATH", "var/yolo-demo"))).resolve()
    gate = threading.Lock()
    state_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        storage.mkdir(parents=True, exist_ok=True)
        # A process interrupted during inference cannot resume its in-memory tracker.
        for state_path in storage.glob("*/state.json"):
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state["status"] in {"queued", "processing"}:
                    state.update(
                        status="failed", message="Server restarted; upload the clip again."
                    )
                    state_path.write_text(json.dumps(state), encoding="utf-8")
            except (ValueError, KeyError, OSError):
                logger.warning("Unreadable demo job state: %s", state_path)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-demo") as pool:
            application.state.pool = pool
            yield

    application = FastAPI(title="MeydanAI YOLO Demo", lifespan=lifespan)
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @application.middleware("http")
    async def same_origin(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if (
            request.method == "POST"
            and origin
            and urlparse(origin).netloc != request.headers.get("host")
        ):
            return JSONResponse(
                {"detail": "Cross-origin uploads are not allowed."}, status_code=403
            )
        size = request.headers.get("content-length", "0")
        if not size.isdigit() or int(size) > MAX_BYTES + 1024 * 1024:
            return JSONResponse({"detail": "Maximum upload size is 500 MB."}, status_code=413)
        return await call_next(request)

    def save_state(directory: Path, state: dict[str, Any]) -> None:
        with state_lock:
            temp = directory / "state.tmp"
            temp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            temp.replace(directory / "state.json")

    def run(directory: Path, source: Path, calibration: Calibration | None) -> None:
        state: dict[str, Any] = {
            "id": directory.name,
            "status": "processing",
            "progress": 0,
            "message": "Başlanır",
        }

        def progress(value: int, message: str) -> None:
            state.update(progress=max(value, state["progress"]), message=message)
            save_state(directory, state)

        try:
            progress(0, "Video yoxlanılır")
            analyze(source, directory, calibration, progress)
            state.update(status="completed", progress=100, message="Analiz tamamlandı")
        except ValueError as error:
            state.update(status="failed", message=str(error))
        except Exception:
            logger.exception("YOLO demo job failed: %s", directory.name)
            state.update(status="failed", message="Analiz alınmadı. Server jurnalını yoxlayın.")
        finally:
            try:
                save_state(directory, state)
            finally:
                gate.release()

    def job_directory(job_id: uuid.UUID) -> Path:
        directory = storage / job_id.hex
        if not (directory / "state.json").is_file():
            raise HTTPException(404, "Job not found.")
        return directory

    @application.get("/")
    def index() -> FileResponse:
        return FileResponse(Path(__file__).with_name("index.html"))

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "max_seconds": int(os.environ.get("DEMO_MAX_SECONDS", "180")),
            "busy": gate.locked(),
        }

    @application.post("/api/jobs", status_code=202)
    async def upload(
        file: Annotated[UploadFile, File()],
        calibration: Annotated[str, Form()] = "",
    ) -> dict[str, Any]:
        parsed = None
        if calibration:
            try:
                parsed = Calibration.model_validate_json(calibration)
            except ValidationError:
                raise HTTPException(
                    422, "Invalid calibration. Check dimensions and four corner points."
                ) from None
        extension = Path(file.filename or "").suffix.lower()
        if extension not in {".mp4", ".mov", ".webm", ".m4v"}:
            raise HTTPException(422, "Upload an MP4, MOV or WebM file.")
        if not gate.acquire(blocking=False):
            raise HTTPException(409, "Another analysis is running. Wait for it to finish.")
        directory = storage / uuid.uuid4().hex
        submitted = False
        try:
            directory.mkdir(parents=True)
            source = directory / f"source{extension}"
            size = 0
            with source.open("xb") as destination:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, "Maximum upload size is 500 MB.")
                    destination.write(chunk)
            if size == 0:
                raise HTTPException(422, "The video is empty.")
            state = {"id": directory.name, "status": "queued", "progress": 0, "message": "Növbədə"}
            save_state(directory, state)
            application.state.pool.submit(run, directory, source, parsed)
            submitted = True
            return state
        finally:
            await file.close()
            if not submitted:
                # Only this newly created UUID directory may be removed on failed upload.
                if directory.parent == storage and directory.exists():
                    shutil.rmtree(directory)
                gate.release()

    @application.get("/api/jobs/{job_id}")
    def status(job_id: uuid.UUID) -> dict[str, Any]:
        directory = job_directory(job_id)
        with state_lock:
            state: dict[str, Any] = json.loads(
                (directory / "state.json").read_text(encoding="utf-8")
            )
            return state

    @application.get("/api/jobs/{job_id}/{artifact}")
    def artifact(job_id: uuid.UUID, artifact: str) -> FileResponse:
        if artifact not in {
            "report.json",
            "tracks.csv",
            "annotated.mp4",
            "heatmap.png",
            "heatmap-group-1.png",
            "heatmap-group-2.png",
        }:
            raise HTTPException(404, "Artifact not found.")
        directory = job_directory(job_id)
        with state_lock:
            state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
        path = directory / artifact
        if state["status"] != "completed" or not path.is_file():
            raise HTTPException(409, "Results are not ready.")
        types = {
            "report.json": "application/json",
            "tracks.csv": "text/csv",
            "annotated.mp4": "video/mp4",
            "heatmap.png": "image/png",
            "heatmap-group-1.png": "image/png",
            "heatmap-group-2.png": "image/png",
        }
        return FileResponse(path, media_type=types[artifact])

    return application


app = create_app()

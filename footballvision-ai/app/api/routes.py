from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.schemas import AnalyzeResponse, CorrectionRequest
from app.core.config import load_config
from app.storage.jobs import JobStore
from app.storage.tasks import analyze_task, run_analysis_job

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=1)


def _store() -> JobStore:
    return JobStore(load_config().sqlite_path)


@router.post("/analyze/upload", response_model=AnalyzeResponse)
async def upload_and_analyze(
    video: UploadFile = File(...),
    config_path: str | None = Form(default=None),
    calibration: str | None = Form(default=None),
) -> AnalyzeResponse:
    config = load_config(config_path)
    root = Path(config.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    store = JobStore(config.sqlite_path)
    job_id = store.create("pending", str(root))
    job_dir = root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(video.filename or "match.mp4").suffix or ".mp4"
    video_path = job_dir / f"source{suffix}"
    video_path.write_bytes(await video.read())
    store.update(job_id, message="uploaded")
    points = json.loads(calibration) if calibration else None
    if analyze_task is not None:
        analyze_task.delay(job_id, str(video_path), str(job_dir), config_path, points)
    else:
        _executor.submit(run_analysis_job, job_id, str(video_path), str(job_dir), config_path, points)
    return AnalyzeResponse(job_id=job_id, status="queued")


@router.get("/analysis/{job_id}")
def get_analysis(job_id: str) -> dict:
    job = _store().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    payload = json.loads(job.result_json) if job.result_json else None
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "result": payload,
    }


@router.get("/analysis/{job_id}/players")
def get_players(job_id: str) -> dict:
    result = _require_result(job_id)
    return {"players": result.get("players", [])}


@router.get("/analysis/{job_id}/events")
def get_events(job_id: str) -> dict:
    result = _require_result(job_id)
    return {"events": result.get("events", [])}


@router.get("/analysis/{job_id}/heatmap/{player_id}")
def get_heatmap(job_id: str, player_id: str):
    result = _require_result(job_id)
    path = result.get("heatmaps", {}).get(str(player_id))
    if not path or not Path(path).is_file():
        raise HTTPException(404, "heatmap not found")
    return FileResponse(path)


@router.get("/analysis/{job_id}/highlights")
def get_highlights(job_id: str) -> dict:
    result = _require_result(job_id)
    return {"highlights": result.get("highlights", [])}


@router.get("/analysis/{job_id}/report")
def get_report(job_id: str):
    result = _require_result(job_id)
    path = result.get("report")
    if not path or not Path(path).is_file():
        raise HTTPException(404, "report not found")
    return FileResponse(path)


@router.patch("/analysis/{job_id}/tracks/{track_id}")
def correct_track(job_id: str, track_id: int, body: CorrectionRequest) -> dict:
    job = _store().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    path = Path(job.output_dir) / "corrections.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    current[str(track_id)] = body.model_dump(exclude_none=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return {"ok": True, "corrections": current}


def _require_result(job_id: str) -> dict:
    job = _store().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if not job.result_json:
        raise HTTPException(409, f"job is {job.status}")
    return json.loads(job.result_json)

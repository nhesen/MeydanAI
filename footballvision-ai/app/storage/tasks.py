from __future__ import annotations

from pathlib import Path

from app.core.config import load_config
from app.pipeline import analyze_video
from app.storage.jobs import JobStore


def run_analysis_job(
    job_id: str,
    video_path: str,
    output_dir: str,
    config_path: str | None = None,
    calibration_points: list[list[float]] | None = None,
) -> None:
    config = load_config(config_path)
    store = JobStore(config.sqlite_path)
    store.update(job_id, status="running", progress=1, message="started")

    def progress(pct: int, message: str) -> None:
        store.update(job_id, status="running", progress=pct, message=message)

    try:
        points = None if not calibration_points else [tuple(item) for item in calibration_points]
        result = analyze_video(
            video_path,
            output_dir,
            config,
            calibration_points=points,
            progress=progress,
        )
        payload = {
            "score": list(result.score),
            "duration_s": result.duration_s,
            "calibrated": result.calibrated,
            "players": [
                {
                    "player_id": item.track_id,
                    "team": item.team.value,
                    "distance_m": item.distance_m,
                    "avg_speed_kmh": item.avg_speed_kmh,
                    "max_speed_kmh": item.max_speed_kmh,
                    "passes": item.passes,
                    "pass_accuracy": item.pass_accuracy,
                    "shots": item.shots,
                    "goals": item.goals,
                    "rating": item.rating,
                    "heatmap": item.heatmap_path,
                    "highlight": item.highlight_path,
                }
                for item in result.players
            ],
            "events": [event.to_dict() for event in result.events],
            "heatmaps": result.heatmaps,
            "highlights": result.highlights,
            "report": result.report_html,
            "annotated_video": result.annotated_video,
            "possession": result.extras.get("possession"),
            "tables": result.extras.get("tables"),
        }
        (Path(output_dir) / "result.json").write_text(
            __import__("json").dumps(payload, indent=2), encoding="utf-8"
        )
        store.update(job_id, status="completed", progress=100, message="done", result=payload)
    except Exception as exc:
        store.update(job_id, status="failed", message="failed", error=str(exc))
        raise


try:
    from celery import Celery

    celery_app = Celery("footballvision", broker=load_config().redis_url, backend=load_config().redis_url)

    @celery_app.task(name="footballvision.analyze")
    def analyze_task(job_id: str, video_path: str, output_dir: str, config_path: str | None = None, calibration_points=None):
        run_analysis_job(job_id, video_path, output_dir, config_path, calibration_points)

except Exception:  # celery is optional; thread fallback is used by the API
    celery_app = None
    analyze_task = None

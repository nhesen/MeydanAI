from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.jobs import JobStore


def test_job_lifecycle_and_missing_result(tmp_path, monkeypatch) -> None:
    db = tmp_path / "jobs.sqlite"
    monkeypatch.setenv("FOOTBALLVISION_SQLITE", str(db))
    store = JobStore(db)
    job_id = store.create("video.mp4", str(tmp_path))
    store.update(job_id, status="completed", progress=100, message="done", result={"players": [], "events": []})
    client = TestClient(create_app())
    missing = client.get("/analysis/does-not-exist")
    assert missing.status_code == 404
    found = client.get(f"/analysis/{job_id}")
    assert found.status_code == 200
    assert found.json()["status"] == "completed"
    players = client.get(f"/analysis/{job_id}/players")
    assert players.status_code == 200
    events = client.get(f"/analysis/{job_id}/events")
    assert events.status_code == 200

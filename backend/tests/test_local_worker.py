import uuid
from collections.abc import Generator
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, get_db
from app.main import create_app
from app.schemas.processing import WorkerAssignmentContext
from app.worker.analyzer import MAX_PLAYER_KMH, MotionTrack, TrackSample, analyze_video, _metrics_for_track
from app.worker.mapping import map_tracks_to_assignments
from app.worker.runner import process_job


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    application = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+psycopg://test:test@localhost:5432/test",
            cors_allowed_origins="http://localhost:3000",
            auth_rate_limit_enabled=False,
            internal_worker_token="test-worker-token",
        )
    )

    def override_db() -> Generator[Session, None, None]:
        yield session

    application.dependency_overrides[get_db] = override_db
    with TestClient(application) as test_client:
        yield test_client


def test_worker_endpoints_require_token(client: TestClient) -> None:
    denied = client.get("/api/v1/internal/processing-jobs")
    assert denied.status_code == 403
    allowed = client.get(
        "/api/v1/internal/processing-jobs",
        headers={"X-Worker-Token": "test-worker-token"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"] == []


def test_motion_analyzer_tracks_moving_blob(tmp_path: Path) -> None:
    video_path = tmp_path / "motion.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
    assert writer.isOpened()
    for index in range(40):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (30 + index * 2, 90), 10, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()

    tracks = analyze_video(video_path)
    assert tracks
    assert tracks[0].activity_count >= 2
    assert tracks[0].distance_m > 0
    assert tracks[0].max_speed_kmh <= MAX_PLAYER_KMH
    assert tracks[0].avg_speed_kmh <= 16
    assert all(0 <= sample.x <= 1 and 0 <= sample.y <= 1 for sample in tracks[0].positions)


def test_metrics_discard_impossible_teleports() -> None:
    track = MotionTrack(
        track_id="track-jump",
        samples=[
            TrackSample(0, 0.20, 0.50),
            TrackSample(250, 0.21, 0.50),
            TrackSample(500, 0.80, 0.50),
            TrackSample(750, 0.81, 0.50),
        ],
    )
    result = _metrics_for_track(track, 1920, 1080)
    assert result.max_speed_kmh <= MAX_PLAYER_KMH
    assert result.avg_speed_kmh <= 16
    assert result.distance_m < 20
    assert result.sprint_count == 0


def test_track_mapping_uses_field_side() -> None:
    from app.worker.analyzer import PlayerMotionResult, TrackSample

    home = WorkerAssignmentContext(
        player_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        team_name="Red",
        side="home",
        jersey_number=3,
        display_name="Home",
    )
    away = WorkerAssignmentContext(
        player_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        team_name="Blue",
        side="away",
        jersey_number=9,
        display_name="Away",
    )
    left = PlayerMotionResult(
        track_id="track-1",
        positions=[TrackSample(0, 0.2, 0.5), TrackSample(200, 0.25, 0.5)],
        rating=6.0,
        distance_m=20,
        avg_speed_kmh=8,
        max_speed_kmh=12,
        sprint_count=0,
        active_seconds=2,
        activity_count=8,
        peak_speed_at_ms=200,
        intensity=[],
        events=[],
        frame_width=320,
        frame_height=180,
    )
    right = PlayerMotionResult(
        track_id="track-2",
        positions=[TrackSample(0, 0.8, 0.5), TrackSample(200, 0.82, 0.5)],
        rating=6.1,
        distance_m=22,
        avg_speed_kmh=9,
        max_speed_kmh=13,
        sprint_count=0,
        active_seconds=2,
        activity_count=9,
        peak_speed_at_ms=200,
        intensity=[],
        events=[],
        frame_width=320,
        frame_height=180,
    )

    paired = map_tracks_to_assignments([left, right], [home, away])
    by_player = {item[0].player_id: item[1].track_id for item in paired}
    assert by_player[home.player_id] == "track-1"
    assert by_player[away.player_id] == "track-2"


class RecordingWorkerApi:
    def __init__(
        self,
        context: dict[str, object],
        roster: list[dict[str, object]] | None = None,
    ) -> None:
        self.context = context
        self.roster = roster
        self.states: list[dict[str, object]] = []
        self.ingests: list[dict[str, object]] = []
        self.roster_requests: list[int] = []

    def list_queued(self) -> list[dict[str, object]]:
        return []

    def get_context(self, job_id: uuid.UUID) -> dict[str, object]:
        return self.context

    def update_state(self, job_id: uuid.UUID, body: dict[str, object]) -> None:
        self.states.append(body)

    def ingest(self, job_id: uuid.UUID, body: dict[str, object], *, idempotency_key: str) -> None:
        self.ingests.append(body)

    def ensure_detected_roster(self, job_id: uuid.UUID, track_count: int) -> dict[str, object]:
        self.roster_requests.append(track_count)
        if self.roster is not None:
            self.context = {**self.context, "assignments": self.roster}
        return self.context


def test_worker_fails_job_without_assignments(tmp_path: Path) -> None:
    job_id = uuid.uuid4()
    api = RecordingWorkerApi(
        {
            "id": str(job_id),
            "match_id": str(uuid.uuid4()),
            "source_reference": "missing.mp4",
            "status": "queued",
            "assignments": [],
        }
    )
    process_job(api, tmp_path, job_id)
    assert api.states[-1]["status"] == "failed"
    assert api.states[-1]["error_code"] == "INVALID_VIDEO"
    assert api.ingests == []
    assert api.roster_requests == []


def test_worker_creates_roster_when_assignments_missing(tmp_path: Path) -> None:
    video_path = tmp_path / "motion.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
    assert writer.isOpened()
    for index in range(40):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (30 + index * 2, 90), 10, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()

    job_id = uuid.uuid4()
    player_id = uuid.uuid4()
    team_id = uuid.uuid4()
    api = RecordingWorkerApi(
        {
            "id": str(job_id),
            "match_id": str(uuid.uuid4()),
            "source_reference": "motion.mp4",
            "status": "queued",
            "assignments": [],
        },
        roster=[
            {
                "player_id": str(player_id),
                "team_id": str(team_id),
                "team_name": "Home",
                "side": "home",
                "jersey_number": 1,
                "display_name": "Detected home 1",
            }
        ],
    )
    process_job(api, tmp_path, job_id)
    assert api.roster_requests
    assert api.ingests
    assert api.states[-1]["status"] != "failed" or api.ingests

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class JobRecord:
    job_id: str
    status: str
    progress: int
    message: str
    video_path: str
    output_dir: str
    result_json: str | None
    error: str | None
    created_at: str


class JobStore:
    def __init__(self, sqlite_path: str | Path) -> None:
        self.path = Path(sqlite_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    video_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create(self, video_path: str, output_dir: str) -> str:
        job_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, progress, message, video_path, output_dir, created_at)
                VALUES (?, 'queued', 0, 'queued', ?, ?, ?)
                """,
                (job_id, video_path, output_dir, datetime.now(UTC).isoformat()),
            )
        return job_id

    def update(self, job_id: str, *, status: str | None = None, progress: int | None = None, message: str | None = None, error: str | None = None, result: dict[str, Any] | None = None) -> None:
        current = self.get(job_id)
        if current is None:
            raise KeyError(job_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs SET status=?, progress=?, message=?, error=?, result_json=?
                WHERE job_id=?
                """,
                (
                    status or current.status,
                    current.progress if progress is None else progress,
                    message or current.message,
                    error if error is not None else current.error,
                    json.dumps(result) if result is not None else current.result_json,
                    job_id,
                ),
            )

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        return JobRecord(**dict(row))

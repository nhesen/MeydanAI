from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any


class WorkerApiError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"Worker API failed with HTTP {status}")
        self.status = status
        self.body = body


class WorkerApi:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def list_queued(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/v1/internal/processing-jobs")
        return list(payload["data"])

    def get_context(self, job_id: uuid.UUID) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/internal/processing-jobs/{job_id}/context")
        return dict(payload["data"])

    def update_state(self, job_id: uuid.UUID, body: dict[str, Any]) -> None:
        self._request("PATCH", f"/api/v1/internal/processing-jobs/{job_id}", body)

    def ensure_detected_roster(self, job_id: uuid.UUID, track_count: int) -> dict[str, Any]:
        payload = self._request(
            "POST",
            f"/api/v1/internal/processing-jobs/{job_id}/detected-roster",
            {"track_count": track_count},
        )
        return dict(payload["data"])

    def ingest(
        self,
        job_id: uuid.UUID,
        body: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> None:
        self._request(
            "POST",
            f"/api/v1/internal/processing-jobs/{job_id}/analytics",
            body,
            extra_headers={"Idempotency-Key": idempotency_key},
        )

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "X-Worker-Token": self.token,
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as error:
            raise WorkerApiError(error.code, error.read().decode()) from error
        return json.loads(raw) if raw else {}


def worker_settings() -> tuple[str, str, str]:
    token = os.environ.get("INTERNAL_WORKER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("INTERNAL_WORKER_TOKEN is required for the local worker")
    base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").strip()
    video_root = os.environ.get("VIDEO_STORAGE_PATH", "./var/videos").strip()
    return base_url, token, video_root

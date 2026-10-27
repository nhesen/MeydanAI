from pathlib import Path

from app.services.recordings import resolve_recording


def test_recording_path_stays_inside_storage(tmp_path: Path) -> None:
    stored = tmp_path / "match.mp4"
    stored.write_bytes(b"video")

    assert resolve_recording(tmp_path, "match.mp4") == stored.resolve()
    assert resolve_recording(tmp_path, "missing.mp4") is None
    assert resolve_recording(tmp_path, "../match.mp4") is None
    assert resolve_recording(tmp_path, "nested/match.mp4") is None
    assert resolve_recording(tmp_path, "match.mov") is None

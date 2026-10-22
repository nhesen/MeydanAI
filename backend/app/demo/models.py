"""Download football-specific Ultralytics weights used by the local demo."""

from __future__ import annotations

from pathlib import Path

PLAYER_DRIVE_ID = "17PXFNlx-jI7VjVo_vQnB1sONjRyvoB-q"
PITCH_DRIVE_ID = "1Ma5Kt86tgpdjCTKfum79YMgNnSjcoOyf"
PLAYER_NAME = "football-player-detection.pt"
PITCH_NAME = "football-pitch-detection.pt"


def model_dir(storage: Path) -> Path:
    directory = storage / "models"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _download(file_id: str, destination: Path) -> None:
    import gdown

    gdown.download(id=file_id, output=str(destination), quiet=False)
    if not destination.is_file() or destination.stat().st_size < 1_000_000:
        destination.unlink(missing_ok=True)
        raise ValueError(f"Football model could not be downloaded: {destination.name}")


def ensure_weight(storage: Path, name: str, file_id: str) -> Path:
    path = model_dir(storage) / name
    if path.is_file() and path.stat().st_size > 1_000_000:
        return path
    _download(file_id, path)
    return path


def player_weights(storage: Path) -> Path:
    return ensure_weight(storage, PLAYER_NAME, PLAYER_DRIVE_ID)


def pitch_weights(storage: Path) -> Path:
    return ensure_weight(storage, PITCH_NAME, PITCH_DRIVE_ID)

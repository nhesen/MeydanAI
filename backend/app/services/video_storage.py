import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.exceptions import DomainError

ALLOWED_VIDEO_TYPES: dict[str, frozenset[str]] = {
    "video/mp4": frozenset({".mp4", ".m4v"}),
    "video/quicktime": frozenset({".mov"}),
    "video/webm": frozenset({".webm"}),
}


@dataclass(frozen=True)
class StoredVideo:
    reference: str
    media_type: str
    size_bytes: int


class VideoStorage(Protocol):
    def store(
        self,
        stream: BinaryIO,
        *,
        original_filename: str,
        media_type: str,
        max_size_bytes: int,
    ) -> StoredVideo: ...

    def delete(self, reference: str) -> None: ...


class LocalVideoStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def store(
        self,
        stream: BinaryIO,
        *,
        original_filename: str,
        media_type: str,
        max_size_bytes: int,
    ) -> StoredVideo:
        extension = Path(original_filename).suffix.lower()
        allowed_extensions = ALLOWED_VIDEO_TYPES.get(media_type)
        if allowed_extensions is None or extension not in allowed_extensions:
            raise self._invalid_video(
                "Upload an MP4, MOV, or WebM video with a matching media type."
            )

        self.root.mkdir(parents=True, exist_ok=True)
        storage_name = f"{uuid.uuid4().hex}{extension}"
        final_path = self.root / storage_name
        temporary_path = self.root / f".{storage_name}.upload"
        size = 0
        signature = b""
        try:
            with temporary_path.open("xb") as destination:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_size_bytes:
                        raise DomainError(
                            status=413,
                            title="Video is too large",
                            detail="The uploaded video exceeds the configured size limit.",
                            error_code="VIDEO_TOO_LARGE",
                        )
                    if len(signature) < 16:
                        signature += chunk[: 16 - len(signature)]
                    destination.write(chunk)
            if size == 0:
                raise self._invalid_video("The uploaded video is empty.")
            if not self._has_valid_signature(media_type, signature):
                raise self._invalid_video(
                    "The file content does not match a supported video format."
                )
            os.replace(temporary_path, final_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return StoredVideo(
            reference=storage_name,
            media_type=media_type,
            size_bytes=size,
        )

    def delete(self, reference: str) -> None:
        candidate = (self.root / reference).resolve()
        if candidate.parent != self.root:
            return
        candidate.unlink(missing_ok=True)

    @staticmethod
    def _has_valid_signature(media_type: str, signature: bytes) -> bool:
        if media_type in {"video/mp4", "video/quicktime"}:
            return len(signature) >= 12 and signature[4:8] == b"ftyp"
        if media_type == "video/webm":
            return signature.startswith(b"\x1a\x45\xdf\xa3")
        return False

    @staticmethod
    def _invalid_video(detail: str) -> DomainError:
        return DomainError(
            status=422,
            title="Invalid video",
            detail=detail,
            error_code="INVALID_VIDEO",
        )

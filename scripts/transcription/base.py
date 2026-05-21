from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .types import TranscriptionRequest, TranscriptionResult


class Transcriber(Protocol):
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        ...


class ArtifactStore(Protocol):
    def upload_file(self, local_path: Path, object_key: str) -> str:
        ...

    def get_signed_download_url(self, object_key: str, expires: int | None = None) -> str:
        ...

    def delete_object(self, object_key: str) -> None:
        ...

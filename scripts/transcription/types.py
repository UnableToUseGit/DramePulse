from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class TranscriptionRequest:
    audio_path: Path
    language_hints: list[str] | None = None
    diarization: bool = False
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    provider: str
    segments: list[TranscriptSegment]
    raw_response_ref: str | None = None
    warnings: list[str] = field(default_factory=list)

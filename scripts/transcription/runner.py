from __future__ import annotations

from pathlib import Path

from .config import AliyunTranscriberConfig
from .providers.aliyun import AliyunTranscriber
from .srt import transcript_segments_to_srt
from .types import TranscriptionRequest


def transcribe_video_to_srt(
    *,
    video_path: Path,
    output_path: Path,
    transcriber: AliyunTranscriber | None = None,
    language_hints: list[str] | None = None,
) -> Path:
    runner = transcriber or AliyunTranscriber(AliyunTranscriberConfig.from_env())
    result = runner.transcribe(
        TranscriptionRequest(
            audio_path=video_path,
            language_hints=language_hints,
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(transcript_segments_to_srt(result.segments), encoding="utf-8")
    return output_path

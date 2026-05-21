from __future__ import annotations

import json
from pathlib import Path

from .config import AliyunTranscriberConfig
from .providers.aliyun import AliyunTranscriber
from .srt import transcript_segments_to_srt
from .types import TranscriptionRequest


def transcribe_video_to_srt(
    *,
    video_path: Path,
    output_path: Path,
    env_path: Path | None = Path(".env"),
    transcriber: AliyunTranscriber | None = None,
    language_hints: list[str] | None = None,
) -> Path:
    runner = transcriber or AliyunTranscriber(AliyunTranscriberConfig.from_env(env_path=env_path))
    result = runner.transcribe(
        TranscriptionRequest(
            audio_path=video_path,
            language_hints=language_hints,
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if result.raw_response is not None:
        raw_output_path = output_path.with_suffix(".transcription.json")
        raw_payload = {
            "provider": result.provider,
            "raw_response": result.raw_response,
        }
        raw_output_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(transcript_segments_to_srt(result.segments), encoding="utf-8")
    return output_path

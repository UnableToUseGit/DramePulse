from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

from ..config import get_settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    confidence: float
    language: str
    duration_ms: int


async def transcribe_upload(audio: UploadFile, duration: float) -> TranscriptionResult:
    settings = get_settings()
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有录到声音，可以再说一次")
    if len(content) > settings.watch_assistant_asr_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="语音太长，请控制在 10 秒以内")

    duration_ms = int(max(0, duration) * 1000)
    backend = settings.watch_assistant_asr_backend
    if backend == "mock":
        return _mock_transcribe(content, duration_ms)
    if backend in {"openai_compatible", "ark"}:
        return _openai_compatible_transcribe(content, audio.filename or "watch-assistant.m4a", duration_ms)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的语音转写后端：{backend}")


def _mock_transcribe(content: bytes, duration_ms: int) -> TranscriptionResult:
    # Local demo and tests use a deterministic fallback so voice plumbing can run without cloud credentials.
    text = "暂停" if content else ""
    return TranscriptionResult(text=text, confidence=0.5, language="zh", duration_ms=duration_ms)


def _openai_compatible_transcribe(content: bytes, filename: str, duration_ms: int) -> TranscriptionResult:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="语音转写服务未配置")

    try:
        from io import BytesIO

        from openai import OpenAI

        audio_file = BytesIO(content)
        audio_file.name = filename
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_api_base)
        response = client.audio.transcriptions.create(
            model=settings.watch_assistant_asr_model,
            file=audio_file,
            response_format="json",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"语音转写失败：{exc}") from exc

    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="没有听清，可以再说一次")
    return TranscriptionResult(text=text, confidence=0.8, language="zh", duration_ms=duration_ms)

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, UploadFile

from ..schemas import WatchAssistantRequest, WatchAssistantResponse, WatchAssistantTranscriptionResponse
from ..watch_assistant import service, transcription

router = APIRouter()


@router.post("/watch-assistant/act", response_model=WatchAssistantResponse)
def act(payload: WatchAssistantRequest) -> dict[str, Any]:
    return service.act(payload)


@router.post("/watch-assistant/transcribe", response_model=WatchAssistantTranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(...),
    series_id: str = Form(...),
    video_id: str = Form(...),
    current_episode: int = Form(...),
    current_time: float = Form(...),
    duration: float = Form(...),
) -> dict[str, Any]:
    result = await transcription.transcribe_upload(audio, duration)
    return {
        "text": result.text,
        "confidence": result.confidence,
        "language": result.language,
        "duration_ms": result.duration_ms,
    }

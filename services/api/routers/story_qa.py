from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..schemas import (
    StoryQaAskRequest,
    StoryQaAskResponse,
    StoryQaCollectionsResponse,
    StoryQaIngestRequest,
    StoryQaIngestResponse,
)
from ..story_qa import service

router = APIRouter()


@router.post("/story-qa/ingest", response_model=StoryQaIngestResponse)
def ingest_story_qa(payload: StoryQaIngestRequest) -> dict[str, Any]:
    try:
        return service.ingest(Path(payload.input_dir), payload.series_id, payload.episode)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/story-qa/ask", response_model=StoryQaAskResponse)
def ask_story_qa(payload: StoryQaAskRequest) -> dict[str, Any]:
    try:
        return service.ask(payload.question, payload.series_id, payload.current_episode, payload.current_time)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/story-qa/collections", response_model=StoryQaCollectionsResponse)
def list_story_qa_collections() -> dict[str, Any]:
    try:
        return service.collections()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

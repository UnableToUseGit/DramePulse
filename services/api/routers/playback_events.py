from __future__ import annotations

from fastapi import APIRouter

from ..repositories.playback_events import create_playback_event
from ..schemas import PlaybackEventCreate, PlaybackEventResponse

router = APIRouter()


@router.post("/playback-events", response_model=PlaybackEventResponse)
def create_event(payload: PlaybackEventCreate) -> PlaybackEventResponse:
    event_id = create_playback_event(payload)
    return PlaybackEventResponse(event_id=event_id, accepted=True)

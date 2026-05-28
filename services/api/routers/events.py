from __future__ import annotations

from fastapi import APIRouter

from ..repositories.user_events import create_user_event
from ..schemas import UserEventCreate, UserEventResponse

router = APIRouter()


@router.post("/events", response_model=UserEventResponse)
def create_event(payload: UserEventCreate) -> UserEventResponse:
    event_id = create_user_event(payload)
    return UserEventResponse(event_id=event_id, accepted=True)

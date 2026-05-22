from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class VideoResponse(BaseModel):
    video_id: str
    title: str
    episode_no: int | None = None
    duration: float | None = None
    stream_url: str
    source: str = "oss"


class VideoListResponse(BaseModel):
    videos: list[VideoResponse]


PlaybackEventType = Literal["pause", "seek_backward", "seek_forward", "playback_rate_change"]


class PlaybackEventCreate(BaseModel):
    event_type: PlaybackEventType
    user_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    client_time: float = Field(ge=0)
    timestamp: int
    extra: dict[str, Any] = Field(default_factory=dict)


class PlaybackEventResponse(BaseModel):
    event_id: str
    accepted: bool

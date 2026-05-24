from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class VideoResponse(BaseModel):
    video_id: str
    series_id: str | None = None
    series_name: str | None = None
    title: str
    episode_no: int | None = None
    episode_label: str | None = None
    duration: float | None = None
    stream_url: str
    danmaku_url: str
    source: str = "oss"
    douyin_video_id: str | None = None


class VideoListResponse(BaseModel):
    videos: list[VideoResponse]


class DanmakuItemResponse(BaseModel):
    danmaku_id: str | None = None
    time_sec: float
    text: str
    digg_count: int | None = None
    score: float | None = None


class DanmakuResponse(BaseModel):
    video_id: str
    available: bool
    count: int
    items: list[DanmakuItemResponse]


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

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StoryChapterResponse(BaseModel):
    chapter_id: str
    video_id: str | None = None
    start_time: float
    end_time: float
    title: str
    summary: str | None = None
    importance: float | None = Field(default=None, ge=0, le=1)


class StoryboardSheetResponse(BaseModel):
    url: str
    start_time: float
    frame_count: int = Field(ge=1)


class StoryboardManifestResponse(BaseModel):
    video_id: str
    interval_seconds: float = Field(gt=0)
    frame_width: int = Field(ge=1)
    frame_height: int = Field(ge=1)
    columns: int = Field(ge=1)
    rows: int = Field(ge=1)
    sheets: list[StoryboardSheetResponse]


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
    story_chapters: list[StoryChapterResponse] | None = None
    storyboard: StoryboardManifestResponse | None = None


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
    danmaku: list["DanmakuItem"] = Field(default_factory=list)


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


class DanmakuItem(BaseModel):
    danmaku_id: str
    video_id: str
    user_id: str | None = None
    client_time: float
    time_ms: int
    text: str
    source: str = "user"
    digg_count: int = 0
    score: float = 0
    status: str = "active"
    raw: dict[str, Any] = Field(default_factory=dict)


class DanmakuListResponse(BaseModel):
    video_id: str
    danmaku: list[DanmakuItem]


class DanmakuCreate(BaseModel):
    user_id: str = Field(min_length=1)
    client_time: float = Field(ge=0)
    text: str = Field(min_length=1)
    extra: dict[str, Any] = Field(default_factory=dict)


class DanmakuCreateResponse(BaseModel):
    danmaku_id: str
    accepted: bool


class InteractionOption(BaseModel):
    option_id: str
    text: str
    danmaku_text: str
    rank: int = Field(ge=1)
    base_score: float | None = Field(default=None, ge=0, le=1)
    status: str = "active"


class InteractionPlan(BaseModel):
    interaction_id: str
    highlight_id: str
    video_id: str
    trigger_time: float = Field(ge=0)
    expire_time: float = Field(ge=0)
    result_time: float = Field(ge=0)
    interaction_type: Literal["danmaku_poll"]
    question: str
    options: list[InteractionOption]
    feedback: dict[str, Any] = Field(default_factory=dict)
    display_position: str = "subtitle_safe_area"
    status: str = "active"


class InteractionPlansResponse(BaseModel):
    video_id: str
    interaction_plans: list[InteractionPlan]


UserEventType = Literal[
    "interaction_exposure",
    "option_click",
    "interaction_dismiss",
    "feedback_shown",
    "replay_click",
    "highlight_jump",
    "pause",
    "resume",
    "seek_forward",
    "seek_backward",
    "playback_rate_change",
    "rewatch_segment",
    "watch_complete",
]


class UserEventCreate(BaseModel):
    event_type: UserEventType
    user_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    highlight_id: str | None = None
    interaction_id: str | None = None
    option_id: str | None = None
    client_time: float = Field(ge=0)
    timestamp: int
    extra: dict[str, Any] = Field(default_factory=dict)


class UserEventResponse(BaseModel):
    event_id: str
    accepted: bool


class InteractionResultOption(BaseModel):
    option_id: str
    text: str
    vote_count: int
    ratio: float


class InteractionResultResponse(BaseModel):
    interaction_id: str
    total_votes: int
    options: list[InteractionResultOption]


class StoryQaIngestRequest(BaseModel):
    input_dir: str = Field(min_length=1)
    series_id: str = Field(min_length=1)
    episode: int = Field(ge=1)


class StoryQaAskRequest(BaseModel):
    question: str = Field(min_length=1)
    series_id: str = Field(min_length=1)
    current_episode: int = Field(ge=1)
    current_time: float = Field(ge=0)


class StoryQaSource(BaseModel):
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryQaAskResponse(BaseModel):
    answer: str
    sources: list[StoryQaSource]


class StoryQaIngestResponse(BaseModel):
    input_dir: str
    series_id: str
    episode: int
    documents: int
    by_type: dict[str, int]
    chroma_dir: str
    collection: str


class StoryQaEpisodeSummary(BaseModel):
    series_id: str | None = None
    episode: int | None = None
    documents: int
    source_types: dict[str, int] = Field(default_factory=dict)


class StoryQaCollectionsResponse(BaseModel):
    collection: str
    chroma_dir: str
    total_documents: int
    episodes: list[StoryQaEpisodeSummary]

from __future__ import annotations

from datetime import datetime
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


class AdminDashboardSummary(BaseModel):
    series_count: int
    episode_count: int
    video_count: int
    video_ready_count: int
    danmaku_episode_count: int
    danmaku_count: int
    interaction_count: int
    event_count: int
    vote_count: int
    click_rate: float
    dismiss_rate: float


class AdminDashboardSeries(BaseModel):
    series_id: str
    series_name: str | None = None
    status: str = "active"
    episode_count: int
    video_ready_count: int
    danmaku_episode_count: int
    danmaku_count: int
    interaction_count: int
    event_count: int
    vote_count: int
    asset_status: str


class AdminDashboardVideo(BaseModel):
    video_id: str
    series_id: str | None = None
    series_name: str | None = None
    title: str
    episode_no: int | None = None
    episode_label: str | None = None
    status: str = "active"
    interaction_count: int
    event_count: int
    vote_count: int
    danmaku_count: int = 0
    has_danmaku: bool = False
    asset_status: str = "missing_danmaku"


class AdminDashboardOption(BaseModel):
    option_id: str
    text: str
    danmaku_text: str
    rank: int
    vote_count: int
    ratio: float


class AdminDashboardInteraction(BaseModel):
    interaction_id: str
    video_id: str
    video_title: str
    highlight_id: str
    trigger_time: float
    expire_time: float
    question: str
    status: str
    exposure_count: int
    click_count: int
    dismiss_count: int
    vote_count: int
    options: list[AdminDashboardOption]


class AdminDashboardEvent(BaseModel):
    event_id: str
    event_type: str
    user_id: str
    video_id: str
    highlight_id: str | None = None
    interaction_id: str | None = None
    option_id: str | None = None
    client_time: float
    server_time: str


class AdminDashboardResponse(BaseModel):
    summary: AdminDashboardSummary
    series: list[AdminDashboardSeries]
    videos: list[AdminDashboardVideo]
    interactions: list[AdminDashboardInteraction]
    recent_events: list[AdminDashboardEvent]


class AdminSeriesCreate(BaseModel):
    series_id: str = Field(min_length=1)
    series_name: str = Field(min_length=1)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AdminAuthResponse(BaseModel):
    authenticated: bool
    username: str | None = None


class AdminSeriesResponse(BaseModel):
    series_id: str
    series_name: str
    name_object_key: str


class AdminSeriesSummary(BaseModel):
    series_id: str
    series_name: str | None = None
    status: str = "active"
    episode_count: int
    min_episode_no: int | None = None
    max_episode_no: int | None = None
    name_object_key: str
    cover_object_key: str


class AdminSeriesEpisode(BaseModel):
    video_id: str
    title: str
    episode_no: int | None = None
    episode_label: str | None = None
    oss_bucket: str
    oss_object_key: str
    douyin_json_path: str | None = None
    content_type: str
    size: int
    status: str
    updated_at: datetime | str | None = None


class AdminSeriesDetail(BaseModel):
    series: AdminSeriesSummary
    episodes: list[AdminSeriesEpisode]


class AdminSeriesListResponse(BaseModel):
    series: list[AdminSeriesSummary]


class AdminSeriesDeleteResponse(BaseModel):
    series_id: str
    deleted_episode_count: int


class AdminSeriesRestoreResponse(BaseModel):
    series_id: str
    restored_episode_count: int


class AdminUploadResponse(BaseModel):
    object_key: str
    content_type: str
    size: int


class AdminEpisodeUploadResponse(BaseModel):
    video_id: str
    series_id: str
    series_name: str
    episode_no: int
    episode_label: str
    title: str
    object_key: str
    content_type: str
    size: int


class AdminDanmakuUploadResponse(BaseModel):
    object_key: str
    content_type: str
    size: int
    danmaku_count: int


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


WatchAssistantActionType = Literal["answer", "seek", "next_episode", "pause", "resume", "noop"]


class WatchAssistantRequest(BaseModel):
    message: str = Field(min_length=1)
    series_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    current_episode: int = Field(ge=1)
    current_time: float = Field(ge=0)
    duration: float = Field(ge=0)
    available_tools: list[str] = Field(default_factory=list)


class WatchAssistantAction(BaseModel):
    type: WatchAssistantActionType
    target_time: float | None = Field(default=None, ge=0)
    relative_seconds: float | None = None
    reason: str | None = None


class WatchAssistantToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ok", "error"] = "ok"
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class WatchAssistantResponse(BaseModel):
    reply: str
    actions: list[WatchAssistantAction] = Field(default_factory=list)
    tool_calls: list[WatchAssistantToolCall] = Field(default_factory=list)
    sources: list[StoryQaSource] = Field(default_factory=list)


class WatchAssistantTranscriptionResponse(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    language: str = "zh"
    duration_ms: int = Field(ge=0)

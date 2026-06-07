from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import (
    admin,
    danmaku,
    dev_logs,
    events,
    feed,
    health,
    interactions,
    playback_events,
    series,
    story_qa,
    videos,
    watch_assistant,
)
from .story_qa import service as story_qa_service


logger = logging.getLogger(__name__)

LOCAL_DEV_CORS_ORIGINS = [
    "http://127.0.0.1:8770",
    "http://localhost:8770",
]


def create_app() -> FastAPI:
    app = FastAPI(title="DramePulse API", version="0.1.0")
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_DEV_CORS_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def warmup_story_qa() -> None:
        try:
            story_qa_service.warmup_lightrag_backend()
        except Exception as exc:
            logger.warning("Story Q&A LightRAG warmup failed; falling back to lazy init: %s", exc)

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(admin.router, prefix="/api", tags=["admin"])
    app.include_router(feed.router, prefix="/api", tags=["feed"])
    app.include_router(series.router, prefix="/api", tags=["series"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(danmaku.router, prefix="/api", tags=["danmaku"])
    app.include_router(interactions.router, prefix="/api", tags=["interactions"])
    app.include_router(events.router, prefix="/api", tags=["events"])
    app.include_router(playback_events.router, prefix="/api", tags=["playback-events"])
    app.include_router(story_qa.router, prefix="/api", tags=["story-qa"])
    app.include_router(dev_logs.router, prefix="/api", tags=["dev-logs"])
    app.include_router(watch_assistant.router, prefix="/api", tags=["watch-assistant"])
    app.mount(
        "/storyboards",
        StaticFiles(directory=str(settings.storyboard_root), check_dir=False),
        name="storyboards",
    )
    return app


app = create_app()

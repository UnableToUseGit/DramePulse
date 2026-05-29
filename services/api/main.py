from __future__ import annotations

import logging

from fastapi import FastAPI

from .routers import danmaku, events, health, interactions, playback_events, story_qa, videos
from .story_qa import service as story_qa_service


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="DramePulse API", version="0.1.0")

    @app.on_event("startup")
    def warmup_story_qa() -> None:
        try:
            story_qa_service.warmup_lightrag_backend()
        except Exception as exc:
            logger.warning("Story Q&A LightRAG warmup failed; falling back to lazy init: %s", exc)

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(danmaku.router, prefix="/api", tags=["danmaku"])
    app.include_router(interactions.router, prefix="/api", tags=["interactions"])
    app.include_router(events.router, prefix="/api", tags=["events"])
    app.include_router(playback_events.router, prefix="/api", tags=["playback-events"])
    app.include_router(story_qa.router, prefix="/api", tags=["story-qa"])
    return app


app = create_app()

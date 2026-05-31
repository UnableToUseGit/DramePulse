from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import danmaku, events, health, interactions, playback_events, story_qa, videos

LOCAL_DEV_CORS_ORIGINS = [
    "http://127.0.0.1:8770",
    "http://localhost:8770",
]


def create_app() -> FastAPI:
    app = FastAPI(title="DramePulse API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_DEV_CORS_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(danmaku.router, prefix="/api", tags=["danmaku"])
    app.include_router(interactions.router, prefix="/api", tags=["interactions"])
    app.include_router(events.router, prefix="/api", tags=["events"])
    app.include_router(playback_events.router, prefix="/api", tags=["playback-events"])
    app.include_router(story_qa.router, prefix="/api", tags=["story-qa"])
    return app


app = create_app()

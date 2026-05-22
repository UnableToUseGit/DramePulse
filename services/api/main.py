from __future__ import annotations

from fastapi import FastAPI

from .routers import health, playback_events, videos


def create_app() -> FastAPI:
    app = FastAPI(title="DramePulse API", version="0.1.0")
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(playback_events.router, prefix="/api", tags=["playback-events"])
    return app


app = create_app()

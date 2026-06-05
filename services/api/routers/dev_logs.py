from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

HOME_FEED_PLAYBACK_LOG_PATH = Path("logs/home-feed-playback.log")
MAX_LOG_LINES_PER_REQUEST = 200
MAX_LOG_LINE_LENGTH = 4000


class HomeFeedPlaybackLogRequest(BaseModel):
    lines: list[str] = Field(default_factory=list, max_length=MAX_LOG_LINES_PER_REQUEST)


@router.post("/dev/home-feed-playback-logs")
def append_home_feed_playback_logs(payload: HomeFeedPlaybackLogRequest) -> dict[str, int | str]:
    HOME_FEED_PLAYBACK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [line[:MAX_LOG_LINE_LENGTH].replace("\n", "\\n") for line in payload.lines]
    with HOME_FEED_PLAYBACK_LOG_PATH.open("a", encoding="utf-8") as file:
        for line in lines:
            file.write(f"{line}\n")
    return {"written": len(lines), "path": str(HOME_FEED_PLAYBACK_LOG_PATH)}

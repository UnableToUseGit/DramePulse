from __future__ import annotations

from fastapi import APIRouter

from ..repositories.videos import list_home_feed_videos
from ..schemas import HomeFeedResponse, VideoResponse

router = APIRouter()


@router.get("/feed/home", response_model=HomeFeedResponse)
def retrieve_home_feed() -> HomeFeedResponse:
    videos = [VideoResponse(**video) for video in list_home_feed_videos()]
    return HomeFeedResponse(videos=videos)

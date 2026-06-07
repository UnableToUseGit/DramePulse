from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..repositories.story_chapters import get_raw_story_chapter_asset, get_story_chapter_payload
from ..repositories.videos import get_video
from ..schemas import StoryChapterRawResponse, StoryChapterResponse

router = APIRouter()


@router.get("/videos/{video_id}/story-chapters", response_model=StoryChapterResponse)
def retrieve_story_chapters(video_id: str) -> StoryChapterResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return StoryChapterResponse(**get_story_chapter_payload(video_id))


@router.get("/videos/{video_id}/story-chapters/raw", response_model=StoryChapterRawResponse)
def retrieve_story_chapters_raw(video_id: str) -> StoryChapterRawResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    payload = get_raw_story_chapter_asset(video_id, "compact")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story chapters raw asset not found")
    return StoryChapterRawResponse(**payload)


@router.get("/videos/{video_id}/story-chapters/debug", response_model=StoryChapterRawResponse)
def retrieve_story_chapters_debug(video_id: str) -> StoryChapterRawResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    payload = get_raw_story_chapter_asset(video_id, "debug")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story chapters debug asset not found")
    return StoryChapterRawResponse(**payload)

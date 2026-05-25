from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..repositories.danmaku import create_danmaku, list_danmaku
from ..repositories.videos import get_video
from ..schemas import DanmakuCreate, DanmakuCreateResponse, DanmakuItem, DanmakuListResponse

router = APIRouter()


@router.get("/videos/{video_id}/danmaku", response_model=DanmakuListResponse)
def retrieve_danmaku(
    video_id: str,
    from_time: float | None = None,
    to_time: float | None = None,
) -> DanmakuListResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    items = [DanmakuItem(**item) for item in list_danmaku(video_id, from_time, to_time)]
    return DanmakuListResponse(video_id=video_id, danmaku=items)


@router.post("/videos/{video_id}/danmaku", response_model=DanmakuCreateResponse)
def post_danmaku(video_id: str, payload: DanmakuCreate) -> DanmakuCreateResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    danmaku_id = create_danmaku(video_id, payload)
    return DanmakuCreateResponse(danmaku_id=danmaku_id, accepted=True)

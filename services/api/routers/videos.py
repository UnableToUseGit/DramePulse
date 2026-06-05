from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Response, status

from ..repositories.danmaku import get_video_danmaku
from ..oss_client import parse_range_header, read_object_range
from ..repositories.videos import get_video, get_video_playback_assets, get_video_storage, list_active_videos
from ..schemas import DanmakuResponse, PlaybackAssetsResponse, VideoListResponse, VideoResponse

router = APIRouter()


@router.get("/videos", response_model=VideoListResponse)
def list_videos() -> VideoListResponse:
    return VideoListResponse(videos=[VideoResponse(**video) for video in list_active_videos()])


@router.get("/videos/{video_id}", response_model=VideoResponse)
def retrieve_video(video_id: str) -> VideoResponse:
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return VideoResponse(**video)


@router.get("/videos/{video_id}/danmaku", response_model=DanmakuResponse)
def retrieve_video_danmaku(video_id: str) -> DanmakuResponse:
    payload = get_video_danmaku(video_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return DanmakuResponse(**payload)


@router.get("/videos/{video_id}/playback-assets", response_model=PlaybackAssetsResponse)
def retrieve_video_playback_assets(video_id: str) -> PlaybackAssetsResponse:
    payload = get_video_playback_assets(video_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return PlaybackAssetsResponse(**payload)


@router.get("/videos/{video_id}/stream")
def stream_video(video_id: str, range_header: str | None = Header(default=None, alias="Range")) -> Response:
    storage = get_video_storage(video_id)
    if not storage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    object_key = str(storage["oss_object_key"])
    bucket_name = str(storage["oss_bucket"])
    content_type = str(storage.get("content_type") or "video/mp4")
    total_size = int(storage.get("size") or 0)
    if total_size <= 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Video size is missing")

    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": content_type,
        "Content-Disposition": "inline",
    }

    try:
        parsed_range = parse_range_header(range_header, total_size)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=str(exc),
            headers={"Content-Range": f"bytes */{total_size}"},
        ) from exc

    try:
        if parsed_range is None:
            body = read_object_range(object_key, bucket_name=bucket_name)
            headers = {**base_headers, "Content-Length": str(len(body))}
            return Response(content=body, status_code=status.HTTP_200_OK, headers=headers, media_type=content_type)

        body = read_object_range(object_key, parsed_range.start, parsed_range.end, bucket_name=bucket_name)
        headers = {
            **base_headers,
            "Content-Length": str(len(body)),
            "Content-Range": f"bytes {parsed_range.start}-{parsed_range.end}/{total_size}",
        }
        return Response(content=body, status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers, media_type=content_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OSS object not found") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "NoSuchKey":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OSS object not found") from exc
        raise

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from ..oss_client import parse_range_header
from ..repositories.new_assets import (
    get_ad_video_storage,
    get_plot_beat_payload,
    get_raw_plot_beat_asset,
    get_video_interaction_payload,
    list_series_ad_slots,
)
from ..repositories.videos import get_video
from ..schemas import (
    PlotBeatResponse,
    RawAssetResponse,
    SeriesAdSlotsResponse,
    VideoInteractionAssetsResponse,
)

router = APIRouter()


@router.get("/videos/{video_id}/plot-beats", response_model=PlotBeatResponse)
def retrieve_plot_beats(video_id: str) -> PlotBeatResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return PlotBeatResponse(**get_plot_beat_payload(video_id))


@router.get("/videos/{video_id}/plot-beats/raw", response_model=RawAssetResponse)
def retrieve_plot_beats_raw(video_id: str) -> RawAssetResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    payload = get_raw_plot_beat_asset(video_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot beats raw asset not found")
    return RawAssetResponse(**payload)


@router.get("/videos/{video_id}/plot-beats/debug", response_model=RawAssetResponse)
def retrieve_plot_beats_debug(video_id: str) -> RawAssetResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    payload = get_raw_plot_beat_asset(video_id, debug=True)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot beats debug asset not found")
    return RawAssetResponse(**payload)


@router.get("/videos/{video_id}/interaction-assets", response_model=VideoInteractionAssetsResponse)
def retrieve_video_interaction_assets(
    video_id: str,
    mode: str | None = Query(default=None, description="Optional interaction mode filter."),
) -> VideoInteractionAssetsResponse:
    if not get_video(video_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return VideoInteractionAssetsResponse(**get_video_interaction_payload(video_id, mode))


@router.get("/series/{series_id}/ad-slots", response_model=SeriesAdSlotsResponse)
def retrieve_series_ad_slots(series_id: str) -> SeriesAdSlotsResponse:
    return SeriesAdSlotsResponse(**list_series_ad_slots(series_id))


@router.get("/ads/{ad_id}/stream")
def stream_ad_video(ad_id: str, range_header: str | None = Header(default=None, alias="Range")) -> Response:
    storage = get_ad_video_storage(ad_id)
    if not storage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")

    source_path = str(storage.get("video_source_path") or "").strip()
    if not source_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad video source not found")

    path = Path(source_path).resolve()
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad video file not found")

    total_size = path.stat().st_size
    if total_size <= 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ad video size is missing")

    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
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

    if parsed_range is None:
        body = path.read_bytes()
        headers = {**base_headers, "Content-Length": str(len(body))}
        return Response(content=body, status_code=status.HTTP_200_OK, headers=headers, media_type="video/mp4")

    with path.open("rb") as handle:
        handle.seek(parsed_range.start)
        body = handle.read(parsed_range.end - parsed_range.start + 1)
    headers = {
        **base_headers,
        "Content-Length": str(len(body)),
        "Content-Range": f"bytes {parsed_range.start}-{parsed_range.end}/{total_size}",
    }
    return Response(content=body, status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers, media_type="video/mp4")

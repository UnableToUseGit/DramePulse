from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..repositories.videos import get_series_episode, list_series, list_series_episodes
from ..schemas import SeriesEpisodesResponse, SeriesListResponse, SeriesSummaryResponse, VideoResponse

router = APIRouter()


@router.get("/series", response_model=SeriesListResponse)
def retrieve_series_list() -> SeriesListResponse:
    series = [SeriesSummaryResponse(**item) for item in list_series()]
    return SeriesListResponse(series=series)


@router.get("/series/{series_id}/episodes", response_model=SeriesEpisodesResponse)
def retrieve_series_episodes(series_id: str) -> SeriesEpisodesResponse:
    payload = list_series_episodes(series_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    return SeriesEpisodesResponse(
        series_id=str(payload["series_id"]),
        series_name=payload.get("series_name"),
        episodes=[VideoResponse(**episode) for episode in payload["episodes"]],
    )


@router.get("/series/{series_id}/episodes/{episode_no}", response_model=VideoResponse)
def retrieve_series_episode(series_id: str, episode_no: int) -> VideoResponse:
    video = get_series_episode(series_id, episode_no)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")
    return VideoResponse(**video)

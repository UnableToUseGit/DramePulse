from __future__ import annotations

import json
import sqlite3
from typing import Any
from urllib.parse import quote

from ..config import get_settings
from ..db import db_cursor, sql_placeholder
from .assets import public_object_url
from .danmaku import get_video_danmaku
from .interactions import list_interaction_plans
from .story_chapters import list_story_chapters


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _table_exists(cursor: Any, table_name: str) -> bool:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    if settings.mode == "local":
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type = 'table' AND name = {placeholder}", (table_name,))
    else:
        cursor.execute(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = {placeholder}
            """,
            (table_name,),
        )
    return cursor.fetchone() is not None


def _video_stream_url(video_id: str, row: dict[str, Any]) -> str:
    settings = get_settings()
    if settings.mode == "cloud" and settings.cdn_base_url:
        object_key = str(row.get("oss_object_key") or "").strip()
        if object_key:
            return f"{settings.cdn_base_url.rstrip('/')}/{quote(object_key, safe='/')}"
    return f"/api/videos/{video_id}/stream"


def _storyboard_sheet_url(video_id: str, url: str) -> str:
    if url.startswith(("http://", "https://", "/")):
        return url
    return f"/storyboards/{quote(video_id, safe='')}/{quote(url)}"


def _to_video_response(row: dict[str, Any]) -> dict[str, Any]:
    video_id = str(row["video_id"])
    stream_url = _video_stream_url(video_id, row)
    source = "cdn" if stream_url.startswith(("http://", "https://")) else row.get("source") or "oss"
    return {
        "video_id": video_id,
        "series_id": row.get("series_id"),
        "series_name": row.get("series_name"),
        "title": row["title"],
        "episode_no": row.get("episode_no"),
        "episode_label": row.get("episode_label"),
        "duration": row.get("duration"),
        "stream_url": stream_url,
        "danmaku_url": f"/api/videos/{video_id}/danmaku",
        "source": source,
        "douyin_video_id": row.get("douyin_video_id"),
    }


def list_active_videos() -> list[dict[str, Any]]:
    settings = get_settings()
    with db_cursor(settings) as cursor:
        cursor.execute(
            """
            SELECT
                video_id,
                series_id,
                series_name,
                title,
                episode_no,
                episode_label,
                duration,
                oss_object_key,
                source,
                douyin_video_id
            FROM videos
            WHERE status = 'active'
            ORDER BY series_id IS NULL, series_id, episode_no IS NULL, episode_no, video_id
            """
        )
        return [_to_video_response(_row_to_dict(row)) for row in cursor.fetchall()]


def list_home_feed_videos() -> list[dict[str, Any]]:
    videos = list_active_videos()
    first_by_series: dict[str, dict[str, Any]] = {}
    for video in videos:
        series_key = str(video.get("series_id") or video["video_id"])
        existing = first_by_series.get(series_key)
        if existing is None or _episode_sort_key(video) < _episode_sort_key(existing):
            first_by_series[series_key] = video
    return sorted(first_by_series.values(), key=lambda video: (str(video.get("series_id") or video["video_id"]), _episode_sort_key(video)))


def _episode_sort_key(video: dict[str, Any]) -> tuple[int, int | str, str]:
    episode_no = video.get("episode_no")
    if episode_no is None:
        return (1, str(video["video_id"]), str(video["video_id"]))
    return (0, int(episode_no), str(video["video_id"]))


def list_series() -> list[dict[str, Any]]:
    settings = get_settings()
    with db_cursor(settings) as cursor:
        has_series_assets = _table_exists(cursor, "series_assets")
        cursor.execute(
            f"""
            SELECT
                COALESCE(NULLIF(v.series_id, ''), v.video_id) AS series_id,
                MAX(v.series_name) AS series_name,
                COUNT(*) AS episode_count,
                {("MAX(a.cover_object_key)" if has_series_assets else "NULL")} AS cover_object_key,
                {("MAX(a.status)" if has_series_assets else "NULL")} AS asset_status
            FROM videos v
            {("LEFT JOIN series_assets a ON a.series_id = COALESCE(NULLIF(v.series_id, ''), v.video_id) AND a.status = 'active'" if has_series_assets else "")}
            WHERE v.status = 'active'
              AND v.series_id IS NOT NULL
              AND v.series_id <> ''
            GROUP BY COALESCE(NULLIF(v.series_id, ''), v.video_id)
            ORDER BY series_id
            """
        )
        rows = [_row_to_dict(row) for row in cursor.fetchall()]

    first_videos = {str(video.get("series_id") or video["video_id"]): video for video in list_home_feed_videos()}
    series: list[dict[str, Any]] = []
    for row in rows:
        series_id = str(row["series_id"])
        first_video = first_videos.get(series_id)
        title = row.get("series_name")
        if not title and first_video:
            title = first_video.get("series_name") or first_video.get("title")
        series.append(
            {
                "series_id": series_id,
                "title": str(title or series_id),
                "cover_url": public_object_url(str(row["cover_object_key"])) if row.get("cover_object_key") else None,
                "summary": None,
                "episode_count": int(row.get("episode_count") or 0),
                "first_video_id": first_video.get("video_id") if first_video else None,
                "status": "active",
            }
        )
    return series


def list_series_episodes(series_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                video_id,
                series_id,
                series_name,
                title,
                episode_no,
                episode_label,
                duration,
                oss_object_key,
                source,
                douyin_video_id
            FROM videos
            WHERE status = 'active'
              AND COALESCE(NULLIF(series_id, ''), video_id) = {placeholder}
            ORDER BY episode_no IS NULL, episode_no, video_id
            """,
            (series_id,),
        )
        videos = [_to_video_response(_row_to_dict(row)) for row in cursor.fetchall()]
    if not videos:
        return None
    return {
        "series_id": series_id,
        "series_name": videos[0].get("series_name"),
        "episodes": videos,
    }


def get_series_episode(series_id: str, episode_no: int) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                video_id,
                series_id,
                series_name,
                title,
                episode_no,
                episode_label,
                duration,
                oss_object_key,
                source,
                douyin_video_id
            FROM videos
            WHERE status = 'active'
              AND COALESCE(NULLIF(series_id, ''), video_id) = {placeholder}
              AND episode_no = {placeholder}
            """,
            (series_id, episode_no),
        )
        row = cursor.fetchone()
        return _to_video_response(_row_to_dict(row)) if row else None


def get_video(video_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                video_id,
                series_id,
                series_name,
                title,
                episode_no,
                episode_label,
                duration,
                oss_object_key,
                source,
                douyin_video_id
            FROM videos
            WHERE video_id = {placeholder} AND status = 'active'
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        return _to_video_response(_row_to_dict(row)) if row else None


def get_video_storyboard(video_id: str) -> dict[str, Any]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            if not _table_exists(cursor, "video_storyboards"):
                return _empty_storyboard(video_id)
            cursor.execute(
                f"""
                SELECT
                    video_id,
                    interval_seconds,
                    frame_width,
                    frame_height,
                    columns_count,
                    rows_count,
                    manifest_json
                FROM video_storyboards
                WHERE video_id = {placeholder}
                  AND status = 'active'
                """,
                (video_id,),
            )
            row = cursor.fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return _empty_storyboard(video_id)
        raise
    if not row:
        return _empty_storyboard(video_id)

    storyboard = _row_to_dict(row)
    manifest_json = storyboard.pop("manifest_json", None)
    manifest = _json_dict(manifest_json)
    raw_sheets = manifest.get("sheets")
    sheets: list[dict[str, Any]] = []
    if isinstance(raw_sheets, list):
        for sheet in raw_sheets:
            if not isinstance(sheet, dict):
                continue
            url = sheet.get("url")
            if isinstance(url, str) and url:
                sheets.append({**sheet, "url": _storyboard_sheet_url(video_id, url)})
    return {
        "video_id": str(storyboard["video_id"]),
        "available": True,
        "interval_seconds": float(storyboard["interval_seconds"]),
        "frame_width": int(storyboard["frame_width"]),
        "frame_height": int(storyboard["frame_height"]),
        "columns": int(storyboard["columns_count"]),
        "rows": int(storyboard["rows_count"]),
        "sheets": sheets,
    }


def _empty_storyboard(video_id: str) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "available": False,
        "interval_seconds": None,
        "frame_width": None,
        "frame_height": None,
        "columns": None,
        "rows": None,
        "sheets": [],
    }


def _json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)


def get_video_playback_assets(video_id: str) -> dict[str, Any] | None:
    video = get_video(video_id)
    if not video:
        return None

    danmaku = get_video_danmaku(video_id)
    if danmaku is None:
        danmaku = {"video_id": video_id, "available": False, "count": 0, "items": [], "danmaku": []}

    return {
        "video": video,
        "danmaku": danmaku,
        "storyboard": get_video_storyboard(video_id),
        "story_chapters": list_story_chapters(video_id),
        "interaction_plans": list_interaction_plans(video_id),
    }


def get_video_storage(video_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT video_id, oss_bucket, oss_object_key, content_type, size
            FROM videos
            WHERE video_id = {placeholder} AND status = 'active'
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None

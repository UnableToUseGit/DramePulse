from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..db import db_cursor, sql_placeholder


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _to_video_response(row: dict[str, Any]) -> dict[str, Any]:
    video_id = str(row["video_id"])
    return {
        "video_id": video_id,
        "series_id": row.get("series_id"),
        "series_name": row.get("series_name"),
        "title": row["title"],
        "episode_no": row.get("episode_no"),
        "episode_label": row.get("episode_label"),
        "duration": row.get("duration"),
        "stream_url": f"/api/videos/{video_id}/stream",
        "danmaku_url": f"/api/videos/{video_id}/danmaku",
        "source": row.get("source") or "oss",
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
                source,
                douyin_video_id
            FROM videos
            WHERE status = 'active'
            ORDER BY series_id IS NULL, series_id, episode_no IS NULL, episode_no, video_id
            """
        )
        return [_to_video_response(_row_to_dict(row)) for row in cursor.fetchall()]


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
                source,
                douyin_video_id
            FROM videos
            WHERE video_id = {placeholder} AND status = 'active'
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        return _to_video_response(_row_to_dict(row)) if row else None


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

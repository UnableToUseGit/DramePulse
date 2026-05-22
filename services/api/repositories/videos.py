from __future__ import annotations

from typing import Any

from ..db import db_cursor


def _to_video_response(row: dict[str, Any]) -> dict[str, Any]:
    video_id = str(row["video_id"])
    return {
        "video_id": video_id,
        "title": row["title"],
        "episode_no": row.get("episode_no"),
        "duration": row.get("duration"),
        "stream_url": f"/api/videos/{video_id}/stream",
        "source": row.get("source") or "oss",
    }


def list_active_videos() -> list[dict[str, Any]]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT video_id, title, episode_no, duration, source
            FROM videos
            WHERE status = 'active'
            ORDER BY episode_no IS NULL, episode_no, video_id
            """
        )
        return [_to_video_response(row) for row in cursor.fetchall()]


def get_video(video_id: str) -> dict[str, Any] | None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT video_id, title, episode_no, duration, source
            FROM videos
            WHERE video_id = %s AND status = 'active'
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        return _to_video_response(row) if row else None


def get_video_storage(video_id: str) -> dict[str, Any] | None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT video_id, oss_bucket, oss_object_key, content_type, size
            FROM videos
            WHERE video_id = %s AND status = 'active'
            """,
            (video_id,),
        )
        return cursor.fetchone()

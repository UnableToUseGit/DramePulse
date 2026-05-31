from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from ..config import get_settings
from ..db import db_cursor, sql_placeholder


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _video_stream_url(video_id: str, row: dict[str, Any]) -> str:
    settings = get_settings()
    if settings.mode == "cloud" and settings.cdn_base_url:
        object_key = str(row.get("oss_object_key") or "").strip()
        if object_key:
            return f"{settings.cdn_base_url.rstrip('/')}/{quote(object_key, safe='/')}"
    return f"/api/videos/{video_id}/stream"


def _read_json_file(path: Any) -> dict[str, Any] | None:
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_story_chapters(video_id: str) -> list[dict[str, Any]] | None:
    settings = get_settings()
    payload = _read_json_file(settings.story_chapter_output_root / video_id / "story_chapters.json")
    raw_chapters = payload.get("story_chapters") if payload else None
    if not isinstance(raw_chapters, list):
        return None
    chapters = [chapter for chapter in raw_chapters if isinstance(chapter, dict)]
    return chapters or None


def _storyboard_sheet_url(video_id: str, url: str) -> str:
    if url.startswith(("http://", "https://", "/")):
        return url
    return f"/storyboards/{quote(video_id, safe='')}/{quote(url)}"


def _load_storyboard(video_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    payload = _read_json_file(settings.storyboard_root / video_id / "storyboard_manifest.json")
    if not payload:
        return None
    raw_sheets = payload.get("sheets")
    if not isinstance(raw_sheets, list):
        return None
    sheets: list[dict[str, Any]] = []
    for sheet in raw_sheets:
        if not isinstance(sheet, dict):
            continue
        url = sheet.get("url")
        if isinstance(url, str) and url:
            sheets.append({**sheet, "url": _storyboard_sheet_url(video_id, url)})
    if not sheets:
        return None
    return {**payload, "sheets": sheets}


def _to_video_response(row: dict[str, Any]) -> dict[str, Any]:
    video_id = str(row["video_id"])
    stream_url = _video_stream_url(video_id, row)
    source = "cdn" if stream_url.startswith(("http://", "https://")) else row.get("source") or "oss"
    response = {
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
    story_chapters = _load_story_chapters(video_id)
    storyboard = _load_storyboard(video_id)
    if story_chapters:
        response["story_chapters"] = story_chapters
    if storyboard:
        response["storyboard"] = storyboard
    return response


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

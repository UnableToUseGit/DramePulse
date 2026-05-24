from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..db import db_cursor, sql_placeholder


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _resolve_local_path(relative_path: str) -> Path:
    settings = get_settings()
    root = settings.local_oss_root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise FileNotFoundError(relative_path)
    return path


def _clean_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "danmaku_id": item.get("danmaku_id"),
        "time_sec": float(item.get("time_sec") or 0),
        "text": str(item.get("text") or ""),
        "digg_count": item.get("digg_count"),
        "score": item.get("score"),
    }


def _load_danmaku_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"douyin json must contain an object: {path}")
    danmaku = data.get("danmaku") or {}
    items = danmaku.get("items") or []
    if not isinstance(items, list):
        raise ValueError(f"douyin danmaku.items must be a list: {path}")
    return sorted(
        [_clean_item(item) for item in items if isinstance(item, dict)],
        key=lambda item: item["time_sec"],
    )


def _get_douyin_json_path(video_id: str) -> str | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT douyin_json_path
            FROM videos
            WHERE video_id = {placeholder} AND status = 'active'
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(video_id)
        return _row_to_dict(row).get("douyin_json_path")


def get_video_danmaku(video_id: str) -> dict[str, Any] | None:
    try:
        relative_path = _get_douyin_json_path(video_id)
    except KeyError:
        return None

    if not relative_path:
        return {"video_id": video_id, "available": False, "count": 0, "items": []}

    items = _load_danmaku_items(_resolve_local_path(str(relative_path)))
    return {
        "video_id": video_id,
        "available": True,
        "count": len(items),
        "items": items,
    }

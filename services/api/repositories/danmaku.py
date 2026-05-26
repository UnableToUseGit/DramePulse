from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from ..config import get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql
from ..schemas import DanmakuCreate


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _row_to_item(row: Any) -> dict[str, Any]:
    data = dict(row)
    raw_json = data.pop("raw_json", None)
    data["raw"] = json.loads(raw_json) if raw_json else {}
    return data


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


def _persisted_item_to_lightweight(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "danmaku_id": item.get("danmaku_id"),
        "time_sec": float(item.get("client_time") or 0),
        "text": str(item.get("text") or ""),
        "digg_count": item.get("digg_count"),
        "score": item.get("score"),
    }


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

    persisted_items = list_danmaku(video_id)
    if persisted_items:
        items = sorted(
            [_persisted_item_to_lightweight(item) for item in persisted_items],
            key=lambda item: (item["time_sec"], str(item.get("danmaku_id") or "")),
        )
        return {
            "video_id": video_id,
            "available": True,
            "count": len(items),
            "items": items,
            "danmaku": persisted_items,
        }

    if not relative_path:
        return {
            "video_id": video_id,
            "available": False,
            "count": 0,
            "items": [],
            "danmaku": persisted_items,
        }

    items = _load_danmaku_items(_resolve_local_path(str(relative_path)))
    return {
        "video_id": video_id,
        "available": True,
        "count": len(items),
        "items": items,
        "danmaku": persisted_items,
    }


def list_danmaku(video_id: str, from_time: float | None = None, to_time: float | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    clauses = [f"video_id = {placeholder}", "status = 'active'"]
    params: list[Any] = [video_id]
    if from_time is not None:
        clauses.append(f"client_time >= {placeholder}")
        params.append(from_time)
    if to_time is not None:
        clauses.append(f"client_time <= {placeholder}")
        params.append(to_time)

    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT danmaku_id, video_id, user_id, client_time, time_ms, text, source, digg_count, score, status, raw_json
                FROM danmaku_items
                WHERE {" AND ".join(clauses)}
                ORDER BY client_time, danmaku_id
                """,
                tuple(params),
            )
            return [_row_to_item(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as exc:
        if "no such table: danmaku_items" in str(exc):
            return []
        raise


def create_danmaku(video_id: str, payload: DanmakuCreate) -> str:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    danmaku_id = f"d_{uuid4().hex}"
    time_ms = int(round(payload.client_time * 1000))
    raw = {"extra": payload.extra}
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            INSERT INTO danmaku_items (
                danmaku_id,
                video_id,
                user_id,
                client_time,
                time_ms,
                text,
                source,
                digg_count,
                score,
                status,
                raw_json,
                created_at
            )
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'user', 0, 0, 'active', {placeholder}, {now_sql})
            """,
            (
                danmaku_id,
                video_id,
                payload.user_id,
                payload.client_time,
                time_ms,
                payload.text,
                json.dumps(raw, ensure_ascii=False),
            ),
        )
    return danmaku_id

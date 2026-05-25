from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from ..config import get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql
from ..schemas import DanmakuCreate


def _row_to_item(row: Any) -> dict[str, Any]:
    data = dict(row)
    raw_json = data.pop("raw_json", None)
    data["raw"] = json.loads(raw_json) if raw_json else {}
    return data


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

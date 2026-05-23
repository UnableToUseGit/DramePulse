from __future__ import annotations

import json
from uuid import uuid4

from ..config import get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql
from ..schemas import PlaybackEventCreate


def create_playback_event(payload: PlaybackEventCreate) -> str:
    event_id = f"evt_{uuid4().hex}"
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            INSERT INTO playback_events (
                event_id,
                event_type,
                user_id,
                video_id,
                client_time,
                timestamp,
                server_time,
                extra_json
            )
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {now_sql}, {placeholder})
            """,
            (
                event_id,
                payload.event_type,
                payload.user_id,
                payload.video_id,
                payload.client_time,
                payload.timestamp,
                json.dumps(payload.extra, ensure_ascii=False),
            ),
        )
    return event_id

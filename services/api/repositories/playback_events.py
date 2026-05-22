from __future__ import annotations

import json
from uuid import uuid4

from ..db import db_cursor
from ..schemas import PlaybackEventCreate


def create_playback_event(payload: PlaybackEventCreate) -> str:
    event_id = f"evt_{uuid4().hex}"
    with db_cursor() as cursor:
        cursor.execute(
            """
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
            VALUES (%s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(6), %s)
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

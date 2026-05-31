from __future__ import annotations

import json
from uuid import uuid4

from ..config import get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql
from ..schemas import UserEventCreate
from .interactions import ensure_vote_is_acceptible, increment_option_vote


def create_user_event(payload: UserEventCreate) -> str:
    if payload.event_type == "option_click":
        ensure_vote_is_acceptible(payload.interaction_id, payload.option_id, payload.client_time)

    event_id = f"evt_{uuid4().hex}"
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            INSERT INTO user_events (
                event_id,
                event_type,
                user_id,
                video_id,
                highlight_id,
                interaction_id,
                option_id,
                client_time,
                timestamp,
                server_time,
                extra_json
            )
            VALUES (
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {now_sql}, {placeholder}
            )
            """,
            (
                event_id,
                payload.event_type,
                payload.user_id,
                payload.video_id,
                payload.highlight_id,
                payload.interaction_id,
                payload.option_id,
                payload.client_time,
                payload.timestamp,
                json.dumps(payload.extra, ensure_ascii=False),
            ),
        )

    if payload.event_type == "option_click" and payload.interaction_id and payload.option_id:
        increment_option_vote(payload.interaction_id, payload.option_id)
    return event_id

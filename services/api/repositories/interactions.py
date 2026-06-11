from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status

from ..config import get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql


def _json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)


def list_interaction_plans(video_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT interaction_id, highlight_id, video_id, trigger_time, expire_time, result_time,
                   interaction_type, question, feedback_json, display_position, status
            FROM interaction_plans
            WHERE video_id = {placeholder}
              AND status = 'active'
              AND interaction_type = 'danmaku_poll'
            ORDER BY trigger_time, interaction_id
            """,
            (video_id,),
        )
        plans = [dict(row) for row in cursor.fetchall()]
        if not plans:
            return []

        interaction_ids = [plan["interaction_id"] for plan in plans]
        placeholders = ", ".join([placeholder] * len(interaction_ids))
        cursor.execute(
            f"""
            SELECT option_id, interaction_id, text, danmaku_text, `rank`, base_score, status
            FROM interaction_options
            WHERE interaction_id IN ({placeholders})
              AND status = 'active'
            ORDER BY interaction_id, `rank`, option_id
            """,
            tuple(interaction_ids),
        )
        options_by_interaction: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            option = dict(row)
            options_by_interaction.setdefault(str(option.pop("interaction_id")), []).append(option)

    for plan in plans:
        interaction_id = str(plan["interaction_id"])
        plan["feedback"] = _json_dict(plan.pop("feedback_json", None))
        plan["options"] = options_by_interaction.get(interaction_id, [])
    return plans


def upsert_interaction_plans(
    video_id: str,
    plans: list[dict[str, Any]],
    *,
    replace_existing: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    option_count = sum(len(plan.get("options") or []) for plan in plans)
    with db_cursor(settings) as cursor:
        disabled_existing_count = 0
        if replace_existing:
            cursor.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM interaction_plans
                WHERE video_id = {placeholder}
                  AND status = 'active'
                """,
                (video_id,),
            )
            row = cursor.fetchone()
            disabled_existing_count = int((dict(row) if isinstance(row, dict) else row)["count"] if row else 0)
            if disabled_existing_count:
                cursor.execute(
                    f"""
                    UPDATE interaction_options
                    SET status = 'disabled', updated_at = {now_sql}
                    WHERE status = 'active'
                      AND interaction_id IN (
                          SELECT interaction_id
                          FROM interaction_plans
                          WHERE video_id = {placeholder}
                            AND status = 'active'
                      )
                    """,
                    (video_id,),
                )
                cursor.execute(
                    f"""
                    UPDATE interaction_plans
                    SET status = 'disabled', updated_at = {now_sql}
                    WHERE video_id = {placeholder}
                      AND status = 'active'
                    """,
                    (video_id,),
                )

        for plan in plans:
            values = (
                plan["interaction_id"],
                plan["highlight_id"],
                video_id,
                plan["trigger_time"],
                plan["expire_time"],
                plan["result_time"],
                plan["interaction_type"],
                plan["question"],
                json.dumps(plan.get("feedback") or {}, ensure_ascii=False),
                plan.get("display_position") or "subtitle_safe_area",
                "active",
            )
            if settings.mode == "local":
                cursor.execute(
                    """
                    INSERT INTO interaction_plans (
                        interaction_id, highlight_id, video_id, trigger_time, expire_time,
                        result_time, interaction_type, question, feedback_json,
                        display_position, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(interaction_id) DO UPDATE SET
                        highlight_id = excluded.highlight_id,
                        video_id = excluded.video_id,
                        trigger_time = excluded.trigger_time,
                        expire_time = excluded.expire_time,
                        result_time = excluded.result_time,
                        interaction_type = excluded.interaction_type,
                        question = excluded.question,
                        feedback_json = excluded.feedback_json,
                        display_position = excluded.display_position,
                        status = excluded.status,
                        updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    """,
                    values,
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO interaction_plans (
                        interaction_id, highlight_id, video_id, trigger_time, expire_time,
                        result_time, interaction_type, question, feedback_json,
                        display_position, status
                    )
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                            {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    ON DUPLICATE KEY UPDATE
                        highlight_id = VALUES(highlight_id),
                        video_id = VALUES(video_id),
                        trigger_time = VALUES(trigger_time),
                        expire_time = VALUES(expire_time),
                        result_time = VALUES(result_time),
                        interaction_type = VALUES(interaction_type),
                        question = VALUES(question),
                        feedback_json = VALUES(feedback_json),
                        display_position = VALUES(display_position),
                        status = VALUES(status),
                        updated_at = {now_sql}
                    """,
                    values,
                )

            for option in plan.get("options") or []:
                option_values = (
                    option["option_id"],
                    plan["interaction_id"],
                    option["text"],
                    option["danmaku_text"],
                    option["rank"],
                    option.get("base_score"),
                    "active",
                )
                if settings.mode == "local":
                    cursor.execute(
                        """
                        INSERT INTO interaction_options (
                            option_id, interaction_id, text, danmaku_text, rank, base_score, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(option_id) DO UPDATE SET
                            interaction_id = excluded.interaction_id,
                            text = excluded.text,
                            danmaku_text = excluded.danmaku_text,
                            rank = excluded.rank,
                            base_score = excluded.base_score,
                            status = excluded.status,
                            updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                        """,
                        option_values,
                    )
                else:
                    cursor.execute(
                        f"""
                        INSERT INTO interaction_options (
                            option_id, interaction_id, text, danmaku_text, `rank`, base_score, status
                        )
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder},
                                {placeholder}, {placeholder}, {placeholder})
                        ON DUPLICATE KEY UPDATE
                            interaction_id = VALUES(interaction_id),
                            text = VALUES(text),
                            danmaku_text = VALUES(danmaku_text),
                            `rank` = VALUES(`rank`),
                            base_score = VALUES(base_score),
                            status = VALUES(status),
                            updated_at = {now_sql}
                        """,
                        option_values,
                    )
    return {
        "video_id": video_id,
        "uploaded_count": len(plans),
        "option_count": option_count,
        "disabled_existing_count": disabled_existing_count,
        "active_count": len(plans),
    }


def get_interaction_plan(interaction_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT interaction_id, video_id, expire_time, status
            FROM interaction_plans
            WHERE interaction_id = {placeholder}
            """,
            (interaction_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def ensure_vote_is_acceptible(interaction_id: str | None, option_id: str | None, client_time: float) -> None:
    if not interaction_id or not option_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="option_click requires interaction_id and option_id",
        )

    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT p.interaction_id, p.expire_time, p.status, o.option_id
            FROM interaction_plans p
            JOIN interaction_options o ON o.interaction_id = p.interaction_id
            WHERE p.interaction_id = {placeholder}
              AND o.option_id = {placeholder}
              AND o.status = 'active'
            """,
            (interaction_id, option_id),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction option not found")
    data = dict(row)
    if data["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interaction is not active")
    if client_time > float(data["expire_time"]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interaction vote has expired")


def increment_option_vote(interaction_id: str, option_id: str) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = "strftime('%Y-%m-%d %H:%M:%f', 'now')" if settings.mode == "local" else "UTC_TIMESTAMP(6)"
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO interaction_option_stats (interaction_id, option_id, vote_count, updated_at)
                VALUES (?, ?, 1, strftime('%Y-%m-%d %H:%M:%f', 'now'))
                ON CONFLICT(interaction_id, option_id) DO UPDATE SET
                    vote_count = vote_count + 1,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                (interaction_id, option_id),
            )
            return

        cursor.execute(
            f"""
            INSERT INTO interaction_option_stats (interaction_id, option_id, vote_count, updated_at)
            VALUES ({placeholder}, {placeholder}, 1, {now_sql})
            ON DUPLICATE KEY UPDATE
                vote_count = vote_count + 1,
                updated_at = {now_sql}
            """,
            (interaction_id, option_id),
        )


def get_interaction_results(interaction_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT interaction_id
            FROM interaction_plans
            WHERE interaction_id = {placeholder}
            """,
            (interaction_id,),
        )
        if not cursor.fetchone():
            return None
        cursor.execute(
            f"""
            SELECT o.option_id, o.text, COALESCE(s.vote_count, 0) AS vote_count
            FROM interaction_options o
            LEFT JOIN interaction_option_stats s
              ON s.interaction_id = o.interaction_id
             AND s.option_id = o.option_id
            WHERE o.interaction_id = {placeholder}
              AND o.status = 'active'
            ORDER BY o.`rank`, o.option_id
            """,
            (interaction_id,),
        )
        options = [dict(row) for row in cursor.fetchall()]

    total_votes = sum(int(option["vote_count"]) for option in options)
    for option in options:
        vote_count = int(option["vote_count"])
        option["vote_count"] = vote_count
        option["ratio"] = vote_count / total_votes if total_votes else 0
    return {"interaction_id": interaction_id, "total_votes": total_votes, "options": options}

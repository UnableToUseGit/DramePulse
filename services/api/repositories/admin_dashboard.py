from __future__ import annotations

from datetime import date, datetime
import sqlite3
from typing import Any

from ..config import get_settings
from ..db import db_cursor, sql_placeholder
from .admin_analysis import latest_analysis_jobs_by_video


DRAMA_OBJECT_KEY_PREFIX = "dramas/%"
MANAGED_VIDEO_STATUSES = ("active", "deleted")


def _rows(cursor: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def _int(value: Any) -> int:
    return int(value or 0)


def _datetime_text(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _table_exists(cursor: Any, table_name: str) -> bool:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    if settings.mode == "local":
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type = 'table' AND name = {placeholder}", (table_name,))
    else:
        cursor.execute(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = {placeholder}
            """,
            (table_name,),
        )
    return cursor.fetchone() is not None


def get_admin_dashboard() -> dict[str, Any]:
    settings = get_settings()
    try:
        with db_cursor(settings) as cursor:
            return _get_admin_dashboard(cursor)
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return _empty_dashboard()


def _empty_dashboard() -> dict[str, Any]:
    return {
        "summary": {
            "series_count": 0,
            "episode_count": 0,
            "video_count": 0,
            "video_ready_count": 0,
            "danmaku_episode_count": 0,
            "danmaku_count": 0,
            "interaction_count": 0,
            "event_count": 0,
            "vote_count": 0,
            "click_rate": 0,
            "dismiss_rate": 0,
        },
        "series": [],
        "videos": [],
        "interactions": [],
        "recent_events": [],
    }


def _get_admin_dashboard(cursor: Any) -> dict[str, Any]:
    placeholder = sql_placeholder(get_settings())
    has_series_assets = _table_exists(cursor, "series_assets")
    has_video_storyboards = _table_exists(cursor, "video_storyboards")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS video_count,
            COUNT(DISTINCT COALESCE(NULLIF(series_id, ''), video_id)) AS series_count,
            SUM(CASE WHEN oss_object_key IS NOT NULL AND oss_object_key <> '' THEN 1 ELSE 0 END) AS video_ready_count,
            SUM(CASE WHEN douyin_json_path IS NOT NULL AND douyin_json_path <> '' THEN 1 ELSE 0 END) AS danmaku_episode_count
        FROM videos
        WHERE status = 'active'
          AND oss_object_key LIKE {placeholder}
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    video_totals = dict(cursor.fetchone() or {})
    video_count = _int(video_totals.get("video_count"))
    series_count = _int(video_totals.get("series_count"))
    video_ready_count = _int(video_totals.get("video_ready_count"))
    danmaku_episode_count = _int(video_totals.get("danmaku_episode_count"))

    cursor.execute(
        f"""
        SELECT COUNT(*) AS interaction_count
        FROM interaction_plans p
        JOIN videos v
          ON v.video_id = p.video_id
        WHERE p.status = 'active'
          AND v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    interaction_count = _int(dict(cursor.fetchone() or {}).get("interaction_count"))

    cursor.execute(
        f"""
        SELECT COUNT(*) AS event_count
        FROM user_events e
        JOIN videos v
          ON v.video_id = e.video_id
        WHERE v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    event_count = _int(dict(cursor.fetchone() or {}).get("event_count"))

    cursor.execute(
        f"""
        SELECT COUNT(*) AS danmaku_count
        FROM danmaku_items d
        JOIN videos v
          ON v.video_id = d.video_id
        WHERE d.status = 'active'
          AND v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    danmaku_count = _int(dict(cursor.fetchone() or {}).get("danmaku_count"))

    cursor.execute(
        f"""
        SELECT COALESCE(SUM(s.vote_count), 0) AS vote_count
        FROM interaction_option_stats s
        JOIN interaction_plans p
          ON p.interaction_id = s.interaction_id
        JOIN videos v
          ON v.video_id = p.video_id
        WHERE p.status = 'active'
          AND v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    vote_count = _int(dict(cursor.fetchone() or {}).get("vote_count"))

    cursor.execute(
        f"""
        SELECT
            SUM(CASE WHEN event_type = 'interaction_exposure' THEN 1 ELSE 0 END) AS exposure_count,
            SUM(CASE WHEN event_type = 'option_click' THEN 1 ELSE 0 END) AS click_count,
            SUM(CASE WHEN event_type = 'interaction_dismiss' THEN 1 ELSE 0 END) AS dismiss_count
        FROM user_events e
        JOIN videos v
          ON v.video_id = e.video_id
        WHERE v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    event_totals = dict(cursor.fetchone() or {})
    exposure_count = _int(event_totals.get("exposure_count"))
    click_count = _int(event_totals.get("click_count"))
    dismiss_count = _int(event_totals.get("dismiss_count"))

    cursor.execute(
        f"""
        SELECT
            v.video_id,
            v.series_id,
            v.series_name,
            v.title,
            v.episode_no,
            v.episode_label,
            v.status,
            COALESCE(interactions.interaction_count, 0) AS interaction_count,
            COALESCE(events.event_count, 0) AS event_count,
            COALESCE(votes.vote_count, 0) AS vote_count,
            COALESCE(danmaku.danmaku_count, 0) AS danmaku_count,
            CASE WHEN v.douyin_json_path IS NOT NULL AND v.douyin_json_path <> '' THEN 1 ELSE 0 END AS has_danmaku
            {", CASE WHEN storyboards.video_id IS NOT NULL THEN 1 ELSE 0 END AS has_storyboard" if has_video_storyboards else ""}
        FROM videos v
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS interaction_count
            FROM interaction_plans
            WHERE status = 'active'
            GROUP BY video_id
        ) interactions
          ON interactions.video_id = v.video_id
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS event_count
            FROM user_events
            GROUP BY video_id
        ) events
          ON events.video_id = v.video_id
        LEFT JOIN (
            SELECT p.video_id, SUM(s.vote_count) AS vote_count
            FROM interaction_plans p
            JOIN interaction_option_stats s
              ON s.interaction_id = p.interaction_id
            WHERE p.status = 'active'
            GROUP BY p.video_id
        ) votes
          ON votes.video_id = v.video_id
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS danmaku_count
            FROM danmaku_items
            WHERE status = 'active'
            GROUP BY video_id
        ) danmaku
          ON danmaku.video_id = v.video_id
        {"LEFT JOIN video_storyboards storyboards ON storyboards.video_id = v.video_id AND storyboards.status = 'active'" if has_video_storyboards else ""}
        WHERE v.status IN ({placeholder}, {placeholder})
          AND v.oss_object_key LIKE {placeholder}
        ORDER BY v.series_id IS NULL, v.series_id, v.episode_no IS NULL, v.episode_no, v.video_id
        """,
        (*MANAGED_VIDEO_STATUSES, DRAMA_OBJECT_KEY_PREFIX),
    )
    videos = _rows(cursor)

    cursor.execute(
        f"""
        SELECT
            COALESCE(NULLIF(v.series_id, ''), v.video_id) AS series_id,
            MAX(v.series_name) AS series_name,
            CASE
                WHEN SUM(CASE WHEN v.status = 'active' THEN 1 ELSE 0 END) > 0 THEN 'active'
                ELSE 'deleted'
            END AS status,
            COUNT(*) AS episode_count,
            SUM(CASE WHEN v.oss_object_key IS NOT NULL AND v.oss_object_key <> '' THEN 1 ELSE 0 END) AS video_ready_count,
            SUM(CASE WHEN v.douyin_json_path IS NOT NULL AND v.douyin_json_path <> '' THEN 1 ELSE 0 END) AS danmaku_episode_count,
            COALESCE(SUM(danmaku.danmaku_count), 0) AS danmaku_count,
            COALESCE(SUM(interactions.interaction_count), 0) AS interaction_count,
            COALESCE(SUM(events.event_count), 0) AS event_count,
            COALESCE(SUM(votes.vote_count), 0) AS vote_count
            {", MAX(series_assets.cover_url) AS cover_url" if has_series_assets else ""}
        FROM videos v
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS danmaku_count
            FROM danmaku_items
            WHERE status = 'active'
            GROUP BY video_id
        ) danmaku
          ON danmaku.video_id = v.video_id
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS interaction_count
            FROM interaction_plans
            WHERE status = 'active'
            GROUP BY video_id
        ) interactions
          ON interactions.video_id = v.video_id
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS event_count
            FROM user_events
            GROUP BY video_id
        ) events
          ON events.video_id = v.video_id
        LEFT JOIN (
            SELECT p.video_id, SUM(s.vote_count) AS vote_count
            FROM interaction_plans p
            JOIN interaction_option_stats s
              ON s.interaction_id = p.interaction_id
            WHERE p.status = 'active'
            GROUP BY p.video_id
        ) votes
          ON votes.video_id = v.video_id
        {"LEFT JOIN series_assets ON series_assets.series_id = COALESCE(NULLIF(v.series_id, ''), v.video_id) AND series_assets.status = 'active'" if has_series_assets else ""}
        WHERE v.status IN ({placeholder}, {placeholder})
          AND v.oss_object_key LIKE {placeholder}
        GROUP BY COALESCE(NULLIF(v.series_id, ''), v.video_id)
        ORDER BY
            CASE WHEN SUM(CASE WHEN v.status = 'active' THEN 1 ELSE 0 END) > 0 THEN 0 ELSE 1 END,
            series_id
        """,
        (*MANAGED_VIDEO_STATUSES, DRAMA_OBJECT_KEY_PREFIX),
    )
    series = _rows(cursor)

    cursor.execute(
        f"""
        SELECT
            p.interaction_id,
            p.video_id,
            v.title AS video_title,
            p.highlight_id,
            p.trigger_time,
            p.expire_time,
            p.question,
            p.status,
            SUM(CASE WHEN e.event_type = 'interaction_exposure' THEN 1 ELSE 0 END) AS exposure_count,
            SUM(CASE WHEN e.event_type = 'option_click' THEN 1 ELSE 0 END) AS click_count,
            SUM(CASE WHEN e.event_type = 'interaction_dismiss' THEN 1 ELSE 0 END) AS dismiss_count,
            COALESCE(votes.vote_count, 0) AS vote_count
        FROM interaction_plans p
        JOIN videos v
          ON v.video_id = p.video_id
        LEFT JOIN user_events e
          ON e.interaction_id = p.interaction_id
        LEFT JOIN (
            SELECT interaction_id, SUM(vote_count) AS vote_count
            FROM interaction_option_stats
            GROUP BY interaction_id
        ) votes
          ON votes.interaction_id = p.interaction_id
        WHERE p.status = 'active'
          AND v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        GROUP BY
            p.interaction_id,
            p.video_id,
            v.title,
            p.highlight_id,
            p.trigger_time,
            p.expire_time,
            p.question,
            p.status,
            votes.vote_count
        ORDER BY p.trigger_time, p.interaction_id
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    interactions = _rows(cursor)

    cursor.execute(
        f"""
        SELECT
            o.interaction_id,
            o.option_id,
            o.text,
            o.danmaku_text,
            o.`rank`,
            COALESCE(s.vote_count, 0) AS vote_count
        FROM interaction_options o
        LEFT JOIN interaction_option_stats s
          ON s.interaction_id = o.interaction_id
         AND s.option_id = o.option_id
        JOIN interaction_plans p
          ON p.interaction_id = o.interaction_id
        JOIN videos v
          ON v.video_id = p.video_id
        WHERE o.status = 'active'
          AND p.status = 'active'
          AND v.status = 'active'
          AND v.oss_object_key LIKE {placeholder}
        ORDER BY o.interaction_id, o.`rank`, o.option_id
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    options_by_interaction: dict[str, list[dict[str, Any]]] = {}
    for option in _rows(cursor):
        interaction_id = str(option.pop("interaction_id"))
        options_by_interaction.setdefault(interaction_id, []).append(option)

    cursor.execute(
        f"""
        SELECT
            event_id,
            event_type,
            user_id,
            video_id,
            highlight_id,
            interaction_id,
            option_id,
            client_time,
            server_time
        FROM user_events
        WHERE video_id IN (
            SELECT video_id
            FROM videos
            WHERE status = 'active'
              AND oss_object_key LIKE {placeholder}
        )
        ORDER BY server_time DESC, event_id DESC
        LIMIT 30
        """,
        (DRAMA_OBJECT_KEY_PREFIX,),
    )
    recent_events = _rows(cursor)
    for event in recent_events:
        event["server_time"] = _datetime_text(event.get("server_time"))

    for video in videos:
        video["interaction_count"] = _int(video.get("interaction_count"))
        video["event_count"] = _int(video.get("event_count"))
        video["vote_count"] = _int(video.get("vote_count"))
        video["danmaku_count"] = _int(video.get("danmaku_count"))
        video["has_danmaku"] = bool(video.get("has_danmaku"))
        video["has_storyboard"] = bool(video.get("has_storyboard")) if has_video_storyboards else False
        if video.get("status") == "deleted":
            video["asset_status"] = "deleted"
        elif not video["has_danmaku"]:
            video["asset_status"] = "missing_danmaku"
        elif not video["interaction_count"]:
            video["asset_status"] = "missing_interaction"
        else:
            video["asset_status"] = "ready"
    _attach_analysis_jobs(videos)

    for row in series:
        row["episode_count"] = _int(row.get("episode_count"))
        row["video_ready_count"] = _int(row.get("video_ready_count"))
        row["danmaku_episode_count"] = _int(row.get("danmaku_episode_count"))
        row["danmaku_count"] = _int(row.get("danmaku_count"))
        row["interaction_count"] = _int(row.get("interaction_count"))
        row["event_count"] = _int(row.get("event_count"))
        row["vote_count"] = _int(row.get("vote_count"))
        row["cover_url"] = row.get("cover_url") if has_series_assets else None
        row["has_cover"] = bool(row.get("cover_url"))
        if row.get("status") == "deleted":
            row["asset_status"] = "deleted"
        elif row["video_ready_count"] < row["episode_count"]:
            row["asset_status"] = "missing_video"
        elif row["danmaku_episode_count"] < row["episode_count"]:
            row["asset_status"] = "missing_danmaku"
        elif row["interaction_count"] == 0:
            row["asset_status"] = "missing_interaction"
        else:
            row["asset_status"] = "ready"

    for interaction in interactions:
        interaction_id = str(interaction["interaction_id"])
        total_votes = _int(interaction.get("vote_count"))
        interaction["exposure_count"] = _int(interaction.get("exposure_count"))
        interaction["click_count"] = _int(interaction.get("click_count"))
        interaction["dismiss_count"] = _int(interaction.get("dismiss_count"))
        interaction["vote_count"] = total_votes
        options = options_by_interaction.get(interaction_id, [])
        for option in options:
            option["rank"] = _int(option.get("rank"))
            option["vote_count"] = _int(option.get("vote_count"))
            option["ratio"] = option["vote_count"] / total_votes if total_votes else 0
        interaction["options"] = options

    return {
        "summary": {
            "series_count": series_count,
            "episode_count": video_count,
            "video_count": video_count,
            "video_ready_count": video_ready_count,
            "danmaku_episode_count": danmaku_episode_count,
            "danmaku_count": danmaku_count,
            "interaction_count": interaction_count,
            "event_count": event_count,
            "vote_count": vote_count,
            "click_rate": click_count / exposure_count if exposure_count else 0,
            "dismiss_rate": dismiss_count / exposure_count if exposure_count else 0,
        },
        "series": series,
        "videos": videos,
        "interactions": interactions,
        "recent_events": recent_events,
    }


def _attach_analysis_jobs(videos: list[dict[str, Any]]) -> None:
    jobs = latest_analysis_jobs_by_video([str(video["video_id"]) for video in videos])
    for video in videos:
        job = jobs.get(str(video["video_id"]))
        video["analysis_status"] = str(job.get("status") if job else "not_started")
        video["analysis_stage"] = job.get("stage") if job else None
        video["analysis_job_id"] = job.get("job_id") if job else None
        video["analysis_result_path"] = job.get("result_text_path") if job else None

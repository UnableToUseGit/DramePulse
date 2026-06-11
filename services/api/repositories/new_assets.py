from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..config import Settings, get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql


def create_new_asset_tables_sqlite(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_plot_beat_assets (
            video_id TEXT PRIMARY KEY,
            source_video_id TEXT NOT NULL,
            source_series_id TEXT NULL,
            canonical_series_id TEXT NULL,
            episode_no INTEGER NULL,
            plot_beats_text TEXT NULL,
            plot_beats_debug_text TEXT NULL,
            plot_beats_sha256 TEXT NULL,
            plot_beats_debug_sha256 TEXT NULL,
            source_dir TEXT NOT NULL,
            plot_beats_source_path TEXT NULL,
            debug_source_path TEXT NULL,
            plot_beats_parse_status TEXT NOT NULL DEFAULT 'unknown',
            debug_parse_status TEXT NOT NULL DEFAULT 'unknown',
            import_status TEXT NOT NULL DEFAULT 'active',
            import_error TEXT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_plot_beat_assets_source ON video_plot_beat_assets (source_video_id)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plot_beats (
            beat_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            chapter_id TEXT NOT NULL,
            beat_index INTEGER NOT NULL,
            beat_type TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            summary TEXT NULL,
            reason TEXT NULL,
            raw_json TEXT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_beats_video_time ON plot_beats (video_id, start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_beats_chapter ON plot_beats (chapter_id, beat_index)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_interaction_assets (
            asset_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            source_video_id TEXT NOT NULL,
            interaction_mode TEXT NOT NULL,
            source_series_id TEXT NULL,
            canonical_series_id TEXT NULL,
            episode_no INTEGER NULL,
            plan_text TEXT NULL,
            selection_text TEXT NULL,
            semantic_clusters_text TEXT NULL,
            plan_sha256 TEXT NULL,
            selection_sha256 TEXT NULL,
            semantic_clusters_sha256 TEXT NULL,
            source_dir TEXT NOT NULL,
            plan_source_path TEXT NULL,
            selection_source_path TEXT NULL,
            semantic_clusters_source_path TEXT NULL,
            plan_parse_status TEXT NOT NULL DEFAULT 'unknown',
            selection_parse_status TEXT NOT NULL DEFAULT 'missing',
            semantic_clusters_parse_status TEXT NOT NULL DEFAULT 'missing',
            import_status TEXT NOT NULL DEFAULT 'active',
            import_error TEXT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            UNIQUE (video_id, interaction_mode),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_interaction_assets_video_mode ON video_interaction_assets (video_id, interaction_mode)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_interaction_items (
            interaction_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            interaction_mode TEXT NOT NULL,
            trigger_time REAL NOT NULL,
            expire_time REAL NOT NULL,
            duration_sec REAL NULL,
            content_json TEXT NOT NULL,
            source_asset_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_interaction_items_video_time ON video_interaction_items (video_id, trigger_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_interaction_items_mode ON video_interaction_items (interaction_mode)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_assets (
            ad_id TEXT PRIMARY KEY,
            video_url TEXT NULL,
            video_source_path TEXT NULL,
            duration REAL NULL,
            sponsor_label TEXT NULL,
            product_name TEXT NULL,
            product_description TEXT NULL,
            character_name TEXT NULL,
            cta_text TEXT NULL,
            price_text TEXT NULL,
            selling_points_json TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS series_ad_slots (
            slot_id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            after_episode_no INTEGER NOT NULL,
            ad_id TEXT NOT NULL,
            source_path TEXT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            FOREIGN KEY (ad_id) REFERENCES ad_assets(ad_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_ad_slots_series_episode ON series_ad_slots (series_id, after_episode_no)")


def create_new_asset_tables_mysql(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_plot_beat_assets (
            video_id VARCHAR(64) PRIMARY KEY,
            source_video_id VARCHAR(128) NOT NULL,
            source_series_id VARCHAR(128) NULL,
            canonical_series_id VARCHAR(128) NULL,
            episode_no INT NULL,
            plot_beats_text LONGTEXT NULL,
            plot_beats_debug_text LONGTEXT NULL,
            plot_beats_sha256 CHAR(64) NULL,
            plot_beats_debug_sha256 CHAR(64) NULL,
            source_dir VARCHAR(1024) NOT NULL,
            plot_beats_source_path VARCHAR(1024) NULL,
            debug_source_path VARCHAR(1024) NULL,
            plot_beats_parse_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            debug_parse_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            import_status VARCHAR(32) NOT NULL DEFAULT 'active',
            import_error TEXT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_video_plot_beat_assets_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_video_plot_beat_assets_source (source_video_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plot_beats (
            beat_id VARCHAR(128) PRIMARY KEY,
            video_id VARCHAR(64) NOT NULL,
            chapter_id VARCHAR(128) NOT NULL,
            beat_index INT NOT NULL,
            beat_type VARCHAR(64) NOT NULL,
            start_time DOUBLE NOT NULL,
            end_time DOUBLE NOT NULL,
            summary TEXT NULL,
            reason TEXT NULL,
            raw_json TEXT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_plot_beats_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_plot_beats_video_time (video_id, start_time),
            KEY idx_plot_beats_chapter (chapter_id, beat_index)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_interaction_assets (
            asset_id VARCHAR(160) PRIMARY KEY,
            video_id VARCHAR(64) NOT NULL,
            source_video_id VARCHAR(128) NOT NULL,
            interaction_mode VARCHAR(64) NOT NULL,
            source_series_id VARCHAR(128) NULL,
            canonical_series_id VARCHAR(128) NULL,
            episode_no INT NULL,
            plan_text LONGTEXT NULL,
            selection_text LONGTEXT NULL,
            semantic_clusters_text LONGTEXT NULL,
            plan_sha256 CHAR(64) NULL,
            selection_sha256 CHAR(64) NULL,
            semantic_clusters_sha256 CHAR(64) NULL,
            source_dir VARCHAR(1024) NOT NULL,
            plan_source_path VARCHAR(1024) NULL,
            selection_source_path VARCHAR(1024) NULL,
            semantic_clusters_source_path VARCHAR(1024) NULL,
            plan_parse_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            selection_parse_status VARCHAR(32) NOT NULL DEFAULT 'missing',
            semantic_clusters_parse_status VARCHAR(32) NOT NULL DEFAULT 'missing',
            import_status VARCHAR(32) NOT NULL DEFAULT 'active',
            import_error TEXT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY uk_video_interaction_assets_video_mode (video_id, interaction_mode),
            CONSTRAINT fk_video_interaction_assets_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_video_interaction_assets_video_mode (video_id, interaction_mode)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_interaction_items (
            interaction_id VARCHAR(128) PRIMARY KEY,
            video_id VARCHAR(64) NOT NULL,
            interaction_mode VARCHAR(64) NOT NULL,
            trigger_time DOUBLE NOT NULL,
            expire_time DOUBLE NOT NULL,
            duration_sec DOUBLE NULL,
            content_json JSON NOT NULL,
            source_asset_id VARCHAR(160) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_video_interaction_items_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_video_interaction_items_video_time (video_id, trigger_time),
            KEY idx_video_interaction_items_mode (interaction_mode)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_assets (
            ad_id VARCHAR(128) PRIMARY KEY,
            video_url VARCHAR(1024) NULL,
            video_source_path VARCHAR(1024) NULL,
            duration DOUBLE NULL,
            sponsor_label VARCHAR(128) NULL,
            product_name VARCHAR(255) NULL,
            product_description TEXT NULL,
            character_name VARCHAR(255) NULL,
            cta_text VARCHAR(128) NULL,
            price_text VARCHAR(128) NULL,
            selling_points_json JSON NOT NULL,
            raw_json JSON NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS series_ad_slots (
            slot_id VARCHAR(128) PRIMARY KEY,
            series_id VARCHAR(128) NOT NULL,
            after_episode_no INT NOT NULL,
            ad_id VARCHAR(128) NOT NULL,
            source_path VARCHAR(1024) NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_series_ad_slots_ad
                FOREIGN KEY (ad_id) REFERENCES ad_assets(ad_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_series_ad_slots_series_episode (series_id, after_episode_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def ensure_new_asset_tables(settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    with db_cursor(resolved) as cursor:
        if resolved.mode == "local":
            create_new_asset_tables_sqlite(cursor)
        else:
            create_new_asset_tables_mysql(cursor)


def list_plot_beats(video_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT beat_id, video_id, chapter_id, beat_index, beat_type, start_time, end_time,
                       summary, reason, status
                FROM plot_beats
                WHERE video_id = {placeholder}
                  AND status = 'active'
                ORDER BY start_time, beat_index, beat_id
                """,
                (video_id,),
            )
            return [_plot_beat_response(dict(row)) for row in cursor.fetchall()]
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise


def get_plot_beat_payload(video_id: str) -> dict[str, Any]:
    asset = get_plot_beat_asset(video_id)
    beats = list_plot_beats(video_id)
    return {
        "video_id": video_id,
        "available": bool(asset or beats),
        "source_video_id": asset.get("source_video_id") if asset else None,
        "source_series_id": asset.get("source_series_id") if asset else None,
        "canonical_series_id": asset.get("canonical_series_id") if asset else None,
        "episode_no": asset.get("episode_no") if asset else None,
        "plot_beats_parse_status": asset.get("plot_beats_parse_status") if asset else None,
        "debug_parse_status": asset.get("debug_parse_status") if asset else None,
        "plot_beats": beats,
    }


def get_plot_beat_asset(video_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT video_id, source_video_id, source_series_id, canonical_series_id, episode_no,
                       plot_beats_parse_status, debug_parse_status
                FROM video_plot_beat_assets
                WHERE video_id = {placeholder}
                  AND import_status = 'active'
                """,
                (video_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        raise


def get_raw_plot_beat_asset(video_id: str, *, debug: bool = False) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    text_column = "plot_beats_debug_text" if debug else "plot_beats_text"
    parse_column = "debug_parse_status" if debug else "plot_beats_parse_status"
    path_column = "debug_source_path" if debug else "plot_beats_source_path"
    sha_column = "plot_beats_debug_sha256" if debug else "plot_beats_sha256"
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT video_id, source_video_id, {text_column} AS content, {parse_column} AS parse_status,
                       {path_column} AS source_path, {sha_column} AS sha256
                FROM video_plot_beat_assets
                WHERE video_id = {placeholder}
                  AND import_status = 'active'
                """,
                (video_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            payload = dict(row)
            if payload.get("content") is None:
                return None
            payload["filename"] = "plot_beats.debug.json" if debug else "plot_beats.json"
            return payload
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        raise


def list_video_interaction_items(video_id: str, mode: str | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    where_mode = f"AND interaction_mode = {placeholder}" if mode else ""
    params: tuple[Any, ...] = (video_id, mode) if mode else (video_id,)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT interaction_id, video_id, interaction_mode, trigger_time, expire_time,
                       duration_sec, content_json, source_asset_id, status
                FROM video_interaction_items
                WHERE video_id = {placeholder}
                  AND status = 'active'
                  {where_mode}
                ORDER BY trigger_time, interaction_id
                """,
                params,
            )
            return [_interaction_item_response(dict(row)) for row in cursor.fetchall()]
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise


def get_video_interaction_payload(video_id: str, mode: str | None = None) -> dict[str, Any]:
    items = list_video_interaction_items(video_id, mode)
    return {
        "video_id": video_id,
        "interaction_mode": mode,
        "available": bool(items),
        "items": items,
    }


def upsert_admin_video_interaction_assets(
    video_id: str,
    payload: dict[str, Any],
    *,
    replace_existing: bool = True,
) -> dict[str, Any]:
    interaction_mode = str(payload["interaction_mode"]).strip()
    asset_id = str(payload.get("asset_id") or f"admin_{video_id}_{interaction_mode}").strip()
    items = [
        {
            **item,
            "video_id": video_id,
            "interaction_mode": interaction_mode,
            "source_asset_id": asset_id,
        }
        for item in payload["items"]
    ]
    asset = {
        "asset_id": asset_id,
        "video_id": video_id,
        "source_video_id": payload.get("source_video_id") or video_id,
        "interaction_mode": interaction_mode,
        "source_series_id": payload.get("source_series_id"),
        "canonical_series_id": payload.get("canonical_series_id"),
        "episode_no": payload.get("episode_no"),
        "plan_text": json.dumps(payload["items"], ensure_ascii=False),
        "selection_text": None,
        "semantic_clusters_text": None,
        "source_dir": "admin_upload",
        "plan_source_path": None,
        "selection_source_path": None,
        "semantic_clusters_source_path": None,
        "plan_parse_status": "parsed",
        "selection_parse_status": "missing",
        "semantic_clusters_parse_status": "missing",
        "import_error": None,
    }
    disabled_existing_count = upsert_video_interaction_asset(asset, items, replace_existing=replace_existing)
    active_count = len(list_video_interaction_items(video_id, interaction_mode))
    return {
        "video_id": video_id,
        "interaction_mode": interaction_mode,
        "uploaded_count": len(items),
        "disabled_existing_count": disabled_existing_count,
        "active_count": active_count,
    }


def list_series_ad_slots(series_id: str) -> dict[str, Any]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT s.slot_id, s.series_id, s.after_episode_no, s.status,
                       a.ad_id, a.video_url, a.video_source_path, a.duration, a.sponsor_label,
                       a.product_name, a.product_description, a.character_name, a.cta_text,
                       a.price_text, a.selling_points_json
                FROM series_ad_slots s
                JOIN ad_assets a ON a.ad_id = s.ad_id
                WHERE s.series_id = {placeholder}
                  AND s.status = 'active'
                  AND a.status = 'active'
                ORDER BY s.after_episode_no, s.slot_id
                """,
                (series_id,),
            )
            slots = [_ad_slot_response(dict(row)) for row in cursor.fetchall()]
            return {"series_id": series_id, "slots": slots}
    except Exception as exc:
        if _is_missing_table_error(exc):
            return {"series_id": series_id, "slots": []}
        raise


def get_ad_video_storage(ad_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT ad_id, video_source_path, video_url
                FROM ad_assets
                WHERE ad_id = {placeholder}
                  AND status = 'active'
                """,
                (ad_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        raise


def upsert_plot_beat_asset(asset: dict[str, Any], beats: list[dict[str, Any]]) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO video_plot_beat_assets (
                    video_id, source_video_id, source_series_id, canonical_series_id, episode_no,
                    plot_beats_text, plot_beats_debug_text, plot_beats_sha256, plot_beats_debug_sha256,
                    source_dir, plot_beats_source_path, debug_source_path, plot_beats_parse_status,
                    debug_parse_status, import_status, import_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    source_video_id = excluded.source_video_id,
                    source_series_id = excluded.source_series_id,
                    canonical_series_id = excluded.canonical_series_id,
                    episode_no = excluded.episode_no,
                    plot_beats_text = excluded.plot_beats_text,
                    plot_beats_debug_text = excluded.plot_beats_debug_text,
                    plot_beats_sha256 = excluded.plot_beats_sha256,
                    plot_beats_debug_sha256 = excluded.plot_beats_debug_sha256,
                    source_dir = excluded.source_dir,
                    plot_beats_source_path = excluded.plot_beats_source_path,
                    debug_source_path = excluded.debug_source_path,
                    plot_beats_parse_status = excluded.plot_beats_parse_status,
                    debug_parse_status = excluded.debug_parse_status,
                    import_status = excluded.import_status,
                    import_error = excluded.import_error,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                _plot_asset_values(asset),
            )
            cursor.execute("UPDATE plot_beats SET status = 'disabled', updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE video_id = ? AND status = 'active'", (asset["video_id"],))
            for beat in beats:
                cursor.execute(
                    """
                    INSERT INTO plot_beats (
                        beat_id, video_id, chapter_id, beat_index, beat_type, start_time, end_time,
                        summary, reason, raw_json, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    ON CONFLICT(beat_id) DO UPDATE SET
                        video_id = excluded.video_id,
                        chapter_id = excluded.chapter_id,
                        beat_index = excluded.beat_index,
                        beat_type = excluded.beat_type,
                        start_time = excluded.start_time,
                        end_time = excluded.end_time,
                        summary = excluded.summary,
                        reason = excluded.reason,
                        raw_json = excluded.raw_json,
                        status = excluded.status,
                        updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    """,
                    _plot_beat_values(beat),
                )
            return

        cursor.execute(
            f"""
            INSERT INTO video_plot_beat_assets (
                video_id, source_video_id, source_series_id, canonical_series_id, episode_no,
                plot_beats_text, plot_beats_debug_text, plot_beats_sha256, plot_beats_debug_sha256,
                source_dir, plot_beats_source_path, debug_source_path, plot_beats_parse_status,
                debug_parse_status, import_status, import_error
            )
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active', {placeholder})
            ON DUPLICATE KEY UPDATE
                source_video_id = VALUES(source_video_id),
                source_series_id = VALUES(source_series_id),
                canonical_series_id = VALUES(canonical_series_id),
                episode_no = VALUES(episode_no),
                plot_beats_text = VALUES(plot_beats_text),
                plot_beats_debug_text = VALUES(plot_beats_debug_text),
                plot_beats_sha256 = VALUES(plot_beats_sha256),
                plot_beats_debug_sha256 = VALUES(plot_beats_debug_sha256),
                source_dir = VALUES(source_dir),
                plot_beats_source_path = VALUES(plot_beats_source_path),
                debug_source_path = VALUES(debug_source_path),
                plot_beats_parse_status = VALUES(plot_beats_parse_status),
                debug_parse_status = VALUES(debug_parse_status),
                import_status = VALUES(import_status),
                import_error = VALUES(import_error),
                updated_at = {now_sql}
            """,
            _plot_asset_values(asset),
        )
        cursor.execute(f"UPDATE plot_beats SET status = 'disabled', updated_at = {now_sql} WHERE video_id = {placeholder} AND status = 'active'", (asset["video_id"],))
        for beat in beats:
            cursor.execute(
                f"""
                INSERT INTO plot_beats (
                    beat_id, video_id, chapter_id, beat_index, beat_type, start_time, end_time,
                    summary, reason, raw_json, status
                )
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                        {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active')
                ON DUPLICATE KEY UPDATE
                    video_id = VALUES(video_id),
                    chapter_id = VALUES(chapter_id),
                    beat_index = VALUES(beat_index),
                    beat_type = VALUES(beat_type),
                    start_time = VALUES(start_time),
                    end_time = VALUES(end_time),
                    summary = VALUES(summary),
                    reason = VALUES(reason),
                    raw_json = VALUES(raw_json),
                    status = VALUES(status),
                    updated_at = {now_sql}
                """,
                _plot_beat_values(beat),
            )


def upsert_video_interaction_asset(asset: dict[str, Any], items: list[dict[str, Any]], *, replace_existing: bool = True) -> int:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO video_interaction_assets (
                    asset_id, video_id, source_video_id, interaction_mode, source_series_id,
                    canonical_series_id, episode_no, plan_text, selection_text, semantic_clusters_text,
                    plan_sha256, selection_sha256, semantic_clusters_sha256, source_dir,
                    plan_source_path, selection_source_path, semantic_clusters_source_path,
                    plan_parse_status, selection_parse_status, semantic_clusters_parse_status,
                    import_status, import_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(video_id, interaction_mode) DO UPDATE SET
                    source_video_id = excluded.source_video_id,
                    source_series_id = excluded.source_series_id,
                    canonical_series_id = excluded.canonical_series_id,
                    episode_no = excluded.episode_no,
                    plan_text = excluded.plan_text,
                    selection_text = excluded.selection_text,
                    semantic_clusters_text = excluded.semantic_clusters_text,
                    plan_sha256 = excluded.plan_sha256,
                    selection_sha256 = excluded.selection_sha256,
                    semantic_clusters_sha256 = excluded.semantic_clusters_sha256,
                    source_dir = excluded.source_dir,
                    plan_source_path = excluded.plan_source_path,
                    selection_source_path = excluded.selection_source_path,
                    semantic_clusters_source_path = excluded.semantic_clusters_source_path,
                    plan_parse_status = excluded.plan_parse_status,
                    selection_parse_status = excluded.selection_parse_status,
                    semantic_clusters_parse_status = excluded.semantic_clusters_parse_status,
                    import_status = excluded.import_status,
                    import_error = excluded.import_error,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                _interaction_asset_values(asset),
            )
            disabled_existing_count = 0
            if replace_existing:
                cursor.execute("UPDATE video_interaction_items SET status = 'disabled', updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE video_id = ? AND interaction_mode = ? AND status = 'active'", (asset["video_id"], asset["interaction_mode"]))
                disabled_existing_count = int(cursor.rowcount or 0)
            for item in items:
                cursor.execute(
                    """
                    INSERT INTO video_interaction_items (
                        interaction_id, video_id, interaction_mode, trigger_time, expire_time,
                        duration_sec, content_json, source_asset_id, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    ON CONFLICT(interaction_id) DO UPDATE SET
                        video_id = excluded.video_id,
                        interaction_mode = excluded.interaction_mode,
                        trigger_time = excluded.trigger_time,
                        expire_time = excluded.expire_time,
                        duration_sec = excluded.duration_sec,
                        content_json = excluded.content_json,
                        source_asset_id = excluded.source_asset_id,
                        status = excluded.status,
                        updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    """,
                    _interaction_item_values(item),
                )
            return disabled_existing_count

        cursor.execute(
            f"""
            INSERT INTO video_interaction_assets (
                asset_id, video_id, source_video_id, interaction_mode, source_series_id,
                canonical_series_id, episode_no, plan_text, selection_text, semantic_clusters_text,
                plan_sha256, selection_sha256, semantic_clusters_sha256, source_dir,
                plan_source_path, selection_source_path, semantic_clusters_source_path,
                plan_parse_status, selection_parse_status, semantic_clusters_parse_status,
                import_status, import_error
            )
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active', {placeholder})
            ON DUPLICATE KEY UPDATE
                source_video_id = VALUES(source_video_id),
                source_series_id = VALUES(source_series_id),
                canonical_series_id = VALUES(canonical_series_id),
                episode_no = VALUES(episode_no),
                plan_text = VALUES(plan_text),
                selection_text = VALUES(selection_text),
                semantic_clusters_text = VALUES(semantic_clusters_text),
                plan_sha256 = VALUES(plan_sha256),
                selection_sha256 = VALUES(selection_sha256),
                semantic_clusters_sha256 = VALUES(semantic_clusters_sha256),
                source_dir = VALUES(source_dir),
                plan_source_path = VALUES(plan_source_path),
                selection_source_path = VALUES(selection_source_path),
                semantic_clusters_source_path = VALUES(semantic_clusters_source_path),
                plan_parse_status = VALUES(plan_parse_status),
                selection_parse_status = VALUES(selection_parse_status),
                semantic_clusters_parse_status = VALUES(semantic_clusters_parse_status),
                import_status = VALUES(import_status),
                import_error = VALUES(import_error),
                updated_at = {now_sql}
            """,
            _interaction_asset_values(asset),
        )
        disabled_existing_count = 0
        if replace_existing:
            cursor.execute(
                f"UPDATE video_interaction_items SET status = 'disabled', updated_at = {now_sql} WHERE video_id = {placeholder} AND interaction_mode = {placeholder} AND status = 'active'",
                (asset["video_id"], asset["interaction_mode"]),
            )
            disabled_existing_count = int(cursor.rowcount or 0)
        for item in items:
            cursor.execute(
                f"""
                INSERT INTO video_interaction_items (
                    interaction_id, video_id, interaction_mode, trigger_time, expire_time,
                    duration_sec, content_json, source_asset_id, status
                )
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active')
                ON DUPLICATE KEY UPDATE
                    video_id = VALUES(video_id),
                    interaction_mode = VALUES(interaction_mode),
                    trigger_time = VALUES(trigger_time),
                    expire_time = VALUES(expire_time),
                    duration_sec = VALUES(duration_sec),
                    content_json = VALUES(content_json),
                    source_asset_id = VALUES(source_asset_id),
                    status = VALUES(status),
                    updated_at = {now_sql}
                """,
                _interaction_item_values(item),
            )
        return disabled_existing_count


def upsert_ad_slots(series_id: str, slots: list[dict[str, Any]], source_path: str, video_source_path: str | None) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        for slot in slots:
            ad = dict(slot["ad"])
            ad_id = str(ad["ad_id"])
            selling_points = ad.get("selling_points") if isinstance(ad.get("selling_points"), list) else []
            raw_json = json.dumps(ad, ensure_ascii=False)
            values = (
                ad_id,
                ad.get("video_url"),
                video_source_path,
                ad.get("duration"),
                ad.get("sponsor_label"),
                ad.get("product_name"),
                ad.get("product_description"),
                ad.get("character_name"),
                ad.get("cta_text"),
                ad.get("price_text"),
                json.dumps(selling_points, ensure_ascii=False),
                raw_json,
            )
            if settings.mode == "local":
                cursor.execute(
                    """
                    INSERT INTO ad_assets (
                        ad_id, video_url, video_source_path, duration, sponsor_label, product_name,
                        product_description, character_name, cta_text, price_text, selling_points_json, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ad_id) DO UPDATE SET
                        video_url = excluded.video_url,
                        video_source_path = excluded.video_source_path,
                        duration = excluded.duration,
                        sponsor_label = excluded.sponsor_label,
                        product_name = excluded.product_name,
                        product_description = excluded.product_description,
                        character_name = excluded.character_name,
                        cta_text = excluded.cta_text,
                        price_text = excluded.price_text,
                        selling_points_json = excluded.selling_points_json,
                        raw_json = excluded.raw_json,
                        status = 'active',
                        updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    """,
                    values,
                )
                cursor.execute(
                    """
                    INSERT INTO series_ad_slots (slot_id, series_id, after_episode_no, ad_id, source_path)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(slot_id) DO UPDATE SET
                        series_id = excluded.series_id,
                        after_episode_no = excluded.after_episode_no,
                        ad_id = excluded.ad_id,
                        source_path = excluded.source_path,
                        status = 'active',
                        updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    """,
                    (slot["slot_id"], series_id, slot["after_episode_no"], ad_id, source_path),
                )
                continue
            cursor.execute(
                f"""
                INSERT INTO ad_assets (
                    ad_id, video_url, video_source_path, duration, sponsor_label, product_name,
                    product_description, character_name, cta_text, price_text, selling_points_json, raw_json
                )
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                        {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ON DUPLICATE KEY UPDATE
                    video_url = VALUES(video_url),
                    video_source_path = VALUES(video_source_path),
                    duration = VALUES(duration),
                    sponsor_label = VALUES(sponsor_label),
                    product_name = VALUES(product_name),
                    product_description = VALUES(product_description),
                    character_name = VALUES(character_name),
                    cta_text = VALUES(cta_text),
                    price_text = VALUES(price_text),
                    selling_points_json = VALUES(selling_points_json),
                    raw_json = VALUES(raw_json),
                    status = 'active',
                    updated_at = {now_sql}
                """,
                values,
            )
            cursor.execute(
                f"""
                INSERT INTO series_ad_slots (slot_id, series_id, after_episode_no, ad_id, source_path)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ON DUPLICATE KEY UPDATE
                    series_id = VALUES(series_id),
                    after_episode_no = VALUES(after_episode_no),
                    ad_id = VALUES(ad_id),
                    source_path = VALUES(source_path),
                    status = 'active',
                    updated_at = {now_sql}
                """,
                (slot["slot_id"], series_id, slot["after_episode_no"], ad_id, source_path),
            )


def _plot_asset_values(asset: dict[str, Any]) -> tuple[Any, ...]:
    return (
        asset["video_id"],
        asset["source_video_id"],
        asset.get("source_series_id"),
        asset.get("canonical_series_id"),
        asset.get("episode_no"),
        asset.get("plot_beats_text"),
        asset.get("plot_beats_debug_text"),
        asset.get("plot_beats_sha256"),
        asset.get("plot_beats_debug_sha256"),
        asset["source_dir"],
        asset.get("plot_beats_source_path"),
        asset.get("debug_source_path"),
        asset.get("plot_beats_parse_status", "unknown"),
        asset.get("debug_parse_status", "unknown"),
        asset.get("import_error"),
    )


def _plot_beat_values(beat: dict[str, Any]) -> tuple[Any, ...]:
    return (
        beat["beat_id"],
        beat["video_id"],
        beat["chapter_id"],
        beat["beat_index"],
        beat["beat_type"],
        beat["start_time"],
        beat["end_time"],
        beat.get("summary"),
        beat.get("reason"),
        beat.get("raw_json"),
    )


def _interaction_asset_values(asset: dict[str, Any]) -> tuple[Any, ...]:
    return (
        asset["asset_id"],
        asset["video_id"],
        asset["source_video_id"],
        asset["interaction_mode"],
        asset.get("source_series_id"),
        asset.get("canonical_series_id"),
        asset.get("episode_no"),
        asset.get("plan_text"),
        asset.get("selection_text"),
        asset.get("semantic_clusters_text"),
        asset.get("plan_sha256"),
        asset.get("selection_sha256"),
        asset.get("semantic_clusters_sha256"),
        asset["source_dir"],
        asset.get("plan_source_path"),
        asset.get("selection_source_path"),
        asset.get("semantic_clusters_source_path"),
        asset.get("plan_parse_status", "unknown"),
        asset.get("selection_parse_status", "missing"),
        asset.get("semantic_clusters_parse_status", "missing"),
        asset.get("import_error"),
    )


def _interaction_item_values(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item["interaction_id"],
        item["video_id"],
        item["interaction_mode"],
        item["trigger_time"],
        item["expire_time"],
        item.get("duration_sec"),
        json.dumps(item.get("content") or {}, ensure_ascii=False),
        item["source_asset_id"],
    )


def _plot_beat_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "beat_id": str(row["beat_id"]),
        "video_id": str(row["video_id"]),
        "chapter_id": str(row["chapter_id"]),
        "beat_index": int(row["beat_index"]),
        "beat_type": str(row["beat_type"]),
        "start_time": float(row["start_time"]),
        "end_time": float(row["end_time"]),
        "summary": row.get("summary"),
        "reason": row.get("reason"),
        "status": row.get("status") or "active",
    }


def _interaction_item_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "interaction_id": str(row["interaction_id"]),
        "video_id": str(row["video_id"]),
        "interaction_mode": str(row["interaction_mode"]),
        "trigger_time": float(row["trigger_time"]),
        "expire_time": float(row["expire_time"]),
        "duration_sec": float(row["duration_sec"]) if row.get("duration_sec") is not None else None,
        "content": _json_dict(row.get("content_json")),
        "source_asset_id": str(row["source_asset_id"]),
        "status": row.get("status") or "active",
    }


def _ad_slot_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_id": str(row["slot_id"]),
        "series_id": str(row["series_id"]),
        "after_episode_no": int(row["after_episode_no"]),
        "status": row.get("status") or "active",
        "ad": {
            "ad_id": str(row["ad_id"]),
            "video_url": row.get("video_url"),
            "stream_url": f"/api/ads/{row['ad_id']}/stream",
            "video_source_path": row.get("video_source_path"),
            "duration": float(row["duration"]) if row.get("duration") is not None else None,
            "sponsor_label": row.get("sponsor_label"),
            "product_name": row.get("product_name"),
            "product_description": row.get("product_description"),
            "character_name": row.get("character_name"),
            "cta_text": row.get("cta_text"),
            "price_text": row.get("price_text"),
            "selling_points": _json_list(row.get("selling_points_json")),
        },
    }


def _json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)


def _json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _is_missing_table_error(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.OperationalError) and "no such table" in str(exc).lower():
        return True
    return exc.__class__.__name__ in {"ProgrammingError", "OperationalError"} and "doesn't exist" in str(exc).lower()

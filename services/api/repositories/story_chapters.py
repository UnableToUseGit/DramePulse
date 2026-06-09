from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

from ..config import Settings, get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql


RawKind = Literal["compact", "debug"]


def create_story_chapter_tables_sqlite(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS series_aliases (
            alias_series_id TEXT PRIMARY KEY,
            canonical_series_id TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            note TEXT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_aliases_canonical ON series_aliases (canonical_series_id)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_story_chapter_assets (
            video_id TEXT PRIMARY KEY,
            source_video_id TEXT NOT NULL,
            source_series_id TEXT NULL,
            canonical_series_id TEXT NULL,
            episode_no INTEGER NULL,
            story_chapters_text TEXT NULL,
            story_chapters_debug_text TEXT NULL,
            story_chapters_sha256 TEXT NULL,
            story_chapters_debug_sha256 TEXT NULL,
            source_dir TEXT NOT NULL,
            compact_source_path TEXT NULL,
            debug_source_path TEXT NULL,
            compact_parse_status TEXT NOT NULL DEFAULT 'unknown',
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_chapter_assets_source_video ON video_story_chapter_assets (source_video_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_chapter_assets_series_episode ON video_story_chapter_assets (canonical_series_id, episode_no)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS story_chapters (
            chapter_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            chapter_index INTEGER NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            title TEXT NULL,
            summary TEXT NULL,
            reason TEXT NULL,
            source TEXT NOT NULL DEFAULT 'subtitle_scene_aligned',
            status TEXT NOT NULL DEFAULT 'active',
            raw_json TEXT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_chapters_video_time ON story_chapters (video_id, start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_chapters_video_index ON story_chapters (video_id, chapter_index)")


def create_story_chapter_tables_mysql(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS series_aliases (
            alias_series_id VARCHAR(128) PRIMARY KEY,
            canonical_series_id VARCHAR(128) NOT NULL,
            source VARCHAR(64) NOT NULL DEFAULT 'manual',
            note VARCHAR(512) NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            KEY idx_series_aliases_canonical (canonical_series_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_story_chapter_assets (
            video_id VARCHAR(64) PRIMARY KEY,
            source_video_id VARCHAR(128) NOT NULL,
            source_series_id VARCHAR(128) NULL,
            canonical_series_id VARCHAR(128) NULL,
            episode_no INT NULL,
            story_chapters_text LONGTEXT NULL,
            story_chapters_debug_text LONGTEXT NULL,
            story_chapters_sha256 CHAR(64) NULL,
            story_chapters_debug_sha256 CHAR(64) NULL,
            source_dir VARCHAR(1024) NOT NULL,
            compact_source_path VARCHAR(1024) NULL,
            debug_source_path VARCHAR(1024) NULL,
            compact_parse_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            debug_parse_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            import_status VARCHAR(32) NOT NULL DEFAULT 'active',
            import_error TEXT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_story_chapter_asset_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_story_chapter_assets_source_video (source_video_id),
            KEY idx_story_chapter_assets_series_episode (canonical_series_id, episode_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS story_chapters (
            chapter_id VARCHAR(128) PRIMARY KEY,
            video_id VARCHAR(64) NOT NULL,
            chapter_index INT NOT NULL,
            start_time DOUBLE NOT NULL,
            end_time DOUBLE NOT NULL,
            title VARCHAR(255) NULL,
            summary TEXT NULL,
            reason TEXT NULL,
            source VARCHAR(64) NOT NULL DEFAULT 'subtitle_scene_aligned',
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            raw_json TEXT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_story_chapters_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_story_chapters_video_time (video_id, start_time),
            KEY idx_story_chapters_video_index (video_id, chapter_index)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def ensure_story_chapter_tables(settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    with db_cursor(resolved) as cursor:
        if resolved.mode == "local":
            create_story_chapter_tables_sqlite(cursor)
        else:
            create_story_chapter_tables_mysql(cursor)


def list_story_chapters(video_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT
                    chapter_id,
                    video_id,
                    chapter_index,
                    start_time,
                    end_time,
                    title,
                    summary,
                    reason,
                    source,
                    status
                FROM story_chapters
                WHERE video_id = {placeholder}
                  AND status = 'active'
                ORDER BY chapter_index, start_time, chapter_id
                """,
                (video_id,),
            )
            return [_chapter_row_to_response(dict(row)) for row in cursor.fetchall()]
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise


def get_story_chapter_asset(video_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT
                    video_id,
                    source_video_id,
                    source_series_id,
                    canonical_series_id,
                    episode_no,
                    compact_parse_status,
                    debug_parse_status,
                    import_status,
                    import_error,
                    story_chapters_sha256,
                    story_chapters_debug_sha256,
                    compact_source_path,
                    debug_source_path
                FROM video_story_chapter_assets
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


def get_raw_story_chapter_asset(video_id: str, kind: RawKind) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    text_column = "story_chapters_debug_text" if kind == "debug" else "story_chapters_text"
    parse_column = "debug_parse_status" if kind == "debug" else "compact_parse_status"
    path_column = "debug_source_path" if kind == "debug" else "compact_source_path"
    sha_column = "story_chapters_debug_sha256" if kind == "debug" else "story_chapters_sha256"
    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                f"""
                SELECT
                    video_id,
                    source_video_id,
                    {text_column} AS content,
                    {parse_column} AS parse_status,
                    {path_column} AS source_path,
                    {sha_column} AS sha256
                FROM video_story_chapter_assets
                WHERE video_id = {placeholder}
                  AND import_status = 'active'
                """,
                (video_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("content") is None:
                return None
            item["filename"] = "story_chapters.debug.json" if kind == "debug" else "story_chapters.json"
            return item
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        raise


def get_story_chapter_payload(video_id: str) -> dict[str, Any]:
    asset = get_story_chapter_asset(video_id)
    chapters = list_story_chapters(video_id)
    return {
        "video_id": video_id,
        "available": bool(asset or chapters),
        "source_video_id": asset.get("source_video_id") if asset else None,
        "source_series_id": asset.get("source_series_id") if asset else None,
        "canonical_series_id": asset.get("canonical_series_id") if asset else None,
        "episode_no": asset.get("episode_no") if asset else None,
        "compact_parse_status": asset.get("compact_parse_status") if asset else None,
        "debug_parse_status": asset.get("debug_parse_status") if asset else None,
        "chapters": chapters,
    }


def upsert_series_alias(alias_series_id: str, canonical_series_id: str, *, source: str = "manual", note: str | None = None) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO series_aliases (alias_series_id, canonical_series_id, source, note)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(alias_series_id) DO UPDATE SET
                    canonical_series_id = excluded.canonical_series_id,
                    source = excluded.source,
                    note = excluded.note,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                (alias_series_id, canonical_series_id, source, note),
            )
            return
        cursor.execute(
            f"""
            INSERT INTO series_aliases (alias_series_id, canonical_series_id, source, note)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
            ON DUPLICATE KEY UPDATE
                canonical_series_id = VALUES(canonical_series_id),
                source = VALUES(source),
                note = VALUES(note),
                updated_at = {now_sql}
            """,
            (alias_series_id, canonical_series_id, source, note),
        )


def upsert_story_chapter_asset(asset: dict[str, Any], chapters: list[dict[str, Any]]) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO video_story_chapter_assets (
                    video_id,
                    source_video_id,
                    source_series_id,
                    canonical_series_id,
                    episode_no,
                    story_chapters_text,
                    story_chapters_debug_text,
                    story_chapters_sha256,
                    story_chapters_debug_sha256,
                    source_dir,
                    compact_source_path,
                    debug_source_path,
                    compact_parse_status,
                    debug_parse_status,
                    import_status,
                    import_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    source_video_id = excluded.source_video_id,
                    source_series_id = excluded.source_series_id,
                    canonical_series_id = excluded.canonical_series_id,
                    episode_no = excluded.episode_no,
                    story_chapters_text = excluded.story_chapters_text,
                    story_chapters_debug_text = excluded.story_chapters_debug_text,
                    story_chapters_sha256 = excluded.story_chapters_sha256,
                    story_chapters_debug_sha256 = excluded.story_chapters_debug_sha256,
                    source_dir = excluded.source_dir,
                    compact_source_path = excluded.compact_source_path,
                    debug_source_path = excluded.debug_source_path,
                    compact_parse_status = excluded.compact_parse_status,
                    debug_parse_status = excluded.debug_parse_status,
                    import_status = excluded.import_status,
                    import_error = excluded.import_error,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                _asset_values(asset),
            )
            cursor.execute(
                """
                UPDATE story_chapters
                SET status = 'disabled',
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                WHERE video_id = ?
                  AND status = 'active'
                """,
                (asset["video_id"],),
            )
            for chapter in chapters:
                cursor.execute(
                    """
                    INSERT INTO story_chapters (
                        chapter_id,
                        video_id,
                        chapter_index,
                        start_time,
                        end_time,
                        title,
                        summary,
                        reason,
                        source,
                        status,
                        raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    ON CONFLICT(chapter_id) DO UPDATE SET
                        video_id = excluded.video_id,
                        chapter_index = excluded.chapter_index,
                        start_time = excluded.start_time,
                        end_time = excluded.end_time,
                        title = excluded.title,
                        summary = excluded.summary,
                        reason = excluded.reason,
                        source = excluded.source,
                        status = excluded.status,
                        raw_json = excluded.raw_json,
                        updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    """,
                    _chapter_values(chapter),
                )
            return

        cursor.execute(
            f"""
            INSERT INTO video_story_chapter_assets (
                video_id,
                source_video_id,
                source_series_id,
                canonical_series_id,
                episode_no,
                story_chapters_text,
                story_chapters_debug_text,
                story_chapters_sha256,
                story_chapters_debug_sha256,
                source_dir,
                compact_source_path,
                debug_source_path,
                compact_parse_status,
                debug_parse_status,
                import_status,
                import_error
            )
            VALUES (
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active', {placeholder}
            )
            ON DUPLICATE KEY UPDATE
                source_video_id = VALUES(source_video_id),
                source_series_id = VALUES(source_series_id),
                canonical_series_id = VALUES(canonical_series_id),
                episode_no = VALUES(episode_no),
                story_chapters_text = VALUES(story_chapters_text),
                story_chapters_debug_text = VALUES(story_chapters_debug_text),
                story_chapters_sha256 = VALUES(story_chapters_sha256),
                story_chapters_debug_sha256 = VALUES(story_chapters_debug_sha256),
                source_dir = VALUES(source_dir),
                compact_source_path = VALUES(compact_source_path),
                debug_source_path = VALUES(debug_source_path),
                compact_parse_status = VALUES(compact_parse_status),
                debug_parse_status = VALUES(debug_parse_status),
                import_status = VALUES(import_status),
                import_error = VALUES(import_error),
                updated_at = {now_sql}
            """,
            _asset_values(asset),
        )
        cursor.execute(
            f"""
            UPDATE story_chapters
            SET status = 'disabled',
                updated_at = {now_sql}
            WHERE video_id = {placeholder}
              AND status = 'active'
            """,
            (asset["video_id"],),
        )
        for chapter in chapters:
            cursor.execute(
                f"""
                INSERT INTO story_chapters (
                    chapter_id,
                    video_id,
                    chapter_index,
                    start_time,
                    end_time,
                    title,
                    summary,
                    reason,
                    source,
                    status,
                    raw_json
                )
                VALUES (
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active', {placeholder}
                )
                ON DUPLICATE KEY UPDATE
                    video_id = VALUES(video_id),
                    chapter_index = VALUES(chapter_index),
                    start_time = VALUES(start_time),
                    end_time = VALUES(end_time),
                    title = VALUES(title),
                    summary = VALUES(summary),
                    reason = VALUES(reason),
                    source = VALUES(source),
                    status = VALUES(status),
                    raw_json = VALUES(raw_json),
                    updated_at = {now_sql}
                """,
                _chapter_values(chapter),
            )


def _asset_values(asset: dict[str, Any]) -> tuple[Any, ...]:
    return (
        asset["video_id"],
        asset["source_video_id"],
        asset.get("source_series_id"),
        asset.get("canonical_series_id"),
        asset.get("episode_no"),
        asset.get("story_chapters_text"),
        asset.get("story_chapters_debug_text"),
        asset.get("story_chapters_sha256"),
        asset.get("story_chapters_debug_sha256"),
        asset["source_dir"],
        asset.get("compact_source_path"),
        asset.get("debug_source_path"),
        asset.get("compact_parse_status", "unknown"),
        asset.get("debug_parse_status", "unknown"),
        asset.get("import_error"),
    )


def _chapter_values(chapter: dict[str, Any]) -> tuple[Any, ...]:
    return (
        chapter["chapter_id"],
        chapter["video_id"],
        chapter["chapter_index"],
        chapter["start_time"],
        chapter["end_time"],
        chapter.get("title"),
        chapter.get("summary"),
        chapter.get("reason"),
        chapter.get("source", "subtitle_scene_aligned"),
        chapter.get("raw_json"),
    )


def _chapter_row_to_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter_id": str(row["chapter_id"]),
        "video_id": str(row["video_id"]),
        "chapter_index": int(row["chapter_index"]),
        "start_time": float(row["start_time"]),
        "end_time": float(row["end_time"]),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "reason": row.get("reason"),
        "source": row.get("source") or "subtitle_scene_aligned",
        "status": row.get("status") or "active",
    }


def _is_missing_table_error(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.OperationalError) and "no such table" in str(exc).lower():
        return True
    return exc.__class__.__name__ in {"ProgrammingError", "OperationalError"} and "doesn't exist" in str(exc).lower()

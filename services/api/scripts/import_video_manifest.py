from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.api.config import Settings, get_settings
from services.api.db import db_cursor, sql_placeholder, utc_now_sql


VIDEO_COLUMNS_SQLITE = {
    "series_id": "TEXT NULL",
    "series_name": "TEXT NULL",
    "episode_label": "TEXT NULL",
    "duration": "REAL NULL",
    "douyin_video_id": "TEXT NULL",
    "douyin_json_path": "TEXT NULL",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}

VIDEO_COLUMNS_MYSQL = {
    "series_id": "VARCHAR(128) NULL",
    "series_name": "VARCHAR(255) NULL",
    "episode_label": "VARCHAR(32) NULL",
    "duration": "DOUBLE NULL",
    "douyin_video_id": "VARCHAR(64) NULL",
    "douyin_json_path": "VARCHAR(512) NULL",
    "created_at": "DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)",
    "updated_at": "DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)",
}


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    if data.get("schema_version") != "video_manifest.v1":
        raise ValueError(f"unsupported manifest schema_version: {data.get('schema_version')}")
    if not isinstance(data.get("videos"), list):
        raise ValueError("manifest videos must be a list")
    return data


def _create_videos_table_sql(settings: Settings) -> str:
    if settings.mode == "local":
        return """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                series_id TEXT NULL,
                series_name TEXT NULL,
                title TEXT NOT NULL,
                episode_no INTEGER NULL,
                episode_label TEXT NULL,
                duration REAL NULL,
                oss_bucket TEXT NOT NULL,
                oss_object_key TEXT NOT NULL,
                douyin_video_id TEXT NULL,
                douyin_json_path TEXT NULL,
                content_type TEXT NOT NULL DEFAULT 'video/mp4',
                size INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'local',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                UNIQUE (oss_bucket, oss_object_key)
            )
        """
    return """
        CREATE TABLE IF NOT EXISTS videos (
            video_id VARCHAR(64) PRIMARY KEY,
            series_id VARCHAR(128) NULL,
            series_name VARCHAR(255) NULL,
            title VARCHAR(255) NOT NULL,
            episode_no INT NULL,
            episode_label VARCHAR(32) NULL,
            duration DOUBLE NULL,
            oss_bucket VARCHAR(255) NOT NULL,
            oss_object_key VARCHAR(512) NOT NULL,
            douyin_video_id VARCHAR(64) NULL,
            douyin_json_path VARCHAR(512) NULL,
            content_type VARCHAR(128) NOT NULL DEFAULT 'video/mp4',
            size BIGINT NOT NULL,
            source VARCHAR(32) NOT NULL DEFAULT 'oss',
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            UNIQUE KEY uk_videos_oss_object (oss_bucket, oss_object_key),
            KEY idx_videos_episode_no (episode_no),
            KEY idx_videos_status (status),
            KEY idx_videos_series_episode (series_id, episode_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """


def _existing_columns(cursor: Any, settings: Settings) -> set[str]:
    if settings.mode == "local":
        cursor.execute("PRAGMA table_info(videos)")
        return {str(row[1]) for row in cursor.fetchall()}
    cursor.execute("SHOW COLUMNS FROM videos")
    return {str(row["Field"]) for row in cursor.fetchall()}


def _existing_indexes(cursor: Any, settings: Settings) -> set[str]:
    if settings.mode == "local":
        cursor.execute("PRAGMA index_list(videos)")
        return {str(row[1]) for row in cursor.fetchall()}
    cursor.execute("SHOW INDEX FROM videos")
    return {str(row["Key_name"]) for row in cursor.fetchall()}


def ensure_video_schema(settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    column_defs = VIDEO_COLUMNS_SQLITE if resolved.mode == "local" else VIDEO_COLUMNS_MYSQL
    with db_cursor(resolved) as cursor:
        cursor.execute(_create_videos_table_sql(resolved))
        existing = _existing_columns(cursor, resolved)
        for column, definition in column_defs.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE videos ADD COLUMN {column} {definition}")
        if resolved.mode == "local":
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_episode_no ON videos (episode_no)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos (status)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_videos_series_episode ON videos (series_id, episode_no)"
            )
        else:
            existing_indexes = _existing_indexes(cursor, resolved)
            if "idx_videos_episode_no" not in existing_indexes:
                cursor.execute("CREATE INDEX idx_videos_episode_no ON videos (episode_no)")
            if "idx_videos_status" not in existing_indexes:
                cursor.execute("CREATE INDEX idx_videos_status ON videos (status)")
            if "idx_videos_series_episode" not in existing_indexes:
                cursor.execute("CREATE INDEX idx_videos_series_episode ON videos (series_id, episode_no)")


def _video_row(entry: dict[str, Any]) -> tuple[Any, ...]:
    storage = entry["storage"]
    douyin = entry["douyin"]
    return (
        entry["video_id"],
        entry["series_id"],
        entry["series_name"],
        entry["title"],
        entry["episode_no"],
        entry["episode_label"],
        entry.get("duration"),
        storage["bucket"],
        storage["object_key"],
        douyin["video_id"],
        douyin["json_path"],
        storage["content_type"],
        storage["size"],
        entry.get("source", "local"),
        entry.get("status", "active"),
    )


def _resolve_manifest_path(data_root: Path, relative_path: str, *, label: str) -> Path:
    root = data_root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{label} escapes data_root: {relative_path}")
    return path


def validate_manifest_files(manifest: dict[str, Any], data_root: Path) -> None:
    for entry in manifest["videos"]:
        video_id = entry.get("video_id", "<unknown>")
        storage = entry["storage"]
        douyin = entry["douyin"]

        video_path = _resolve_manifest_path(data_root, storage["object_key"], label="video file")
        if not video_path.is_file():
            raise FileNotFoundError(f"Missing video file for {video_id}: {video_path}")

        if douyin.get("available", True):
            douyin_path = _resolve_manifest_path(data_root, douyin["json_path"], label="douyin json")
            if not douyin_path.is_file():
                raise FileNotFoundError(f"Missing douyin json for {video_id}: {douyin_path}")


def _upsert_sql(settings: Settings) -> str:
    now_sql = utc_now_sql(settings)
    if settings.mode == "local":
        return f"""
            INSERT INTO videos (
                video_id, series_id, series_name, title, episode_no, episode_label,
                duration, oss_bucket, oss_object_key, douyin_video_id, douyin_json_path,
                content_type, size, source, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                series_id = excluded.series_id,
                series_name = excluded.series_name,
                title = excluded.title,
                episode_no = excluded.episode_no,
                episode_label = excluded.episode_label,
                duration = excluded.duration,
                oss_bucket = excluded.oss_bucket,
                oss_object_key = excluded.oss_object_key,
                douyin_video_id = excluded.douyin_video_id,
                douyin_json_path = excluded.douyin_json_path,
                content_type = excluded.content_type,
                size = excluded.size,
                source = excluded.source,
                status = excluded.status,
                updated_at = {now_sql}
        """
    return """
        INSERT INTO videos (
            video_id, series_id, series_name, title, episode_no, episode_label,
            duration, oss_bucket, oss_object_key, douyin_video_id, douyin_json_path,
            content_type, size, source, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            series_id = VALUES(series_id),
            series_name = VALUES(series_name),
            title = VALUES(title),
            episode_no = VALUES(episode_no),
            episode_label = VALUES(episode_label),
            duration = VALUES(duration),
            oss_bucket = VALUES(oss_bucket),
            oss_object_key = VALUES(oss_object_key),
            douyin_video_id = VALUES(douyin_video_id),
            douyin_json_path = VALUES(douyin_json_path),
            content_type = VALUES(content_type),
            size = VALUES(size),
            source = VALUES(source),
            status = VALUES(status),
            updated_at = UTC_TIMESTAMP(6)
    """


def import_video_manifest(manifest_path: Path, data_root: Path | None = None) -> int:
    manifest = load_manifest(manifest_path)
    validate_manifest_files(manifest, data_root or manifest_path.parent)
    ensure_video_schema()
    settings = get_settings()
    with db_cursor(settings) as cursor:
        sql = _upsert_sql(settings)
        for entry in manifest["videos"]:
            cursor.execute(sql, _video_row(entry))
    return len(manifest["videos"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import video_manifest.json into videos table.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    count = import_video_manifest(args.manifest, data_root=args.data_root)
    print(f"Imported {count} videos from {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

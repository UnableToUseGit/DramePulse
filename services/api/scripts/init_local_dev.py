from __future__ import annotations

import sqlite3

from services.api.config import get_settings


DEMO_VIDEO_ID = "demo_ep01"
DEMO_VIDEO_TITLE = "DramePulse Demo Episode 01"
DEMO_VIDEO_OBJECT_KEY = "demo_video.mp4"

VIDEO_COLUMNS = {
    "series_id": "TEXT NULL",
    "series_name": "TEXT NULL",
    "episode_label": "TEXT NULL",
    "douyin_video_id": "TEXT NULL",
    "douyin_json_path": "TEXT NULL",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}


def migrate_videos_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("PRAGMA table_info(videos)")
    existing = {str(row[1]) for row in cursor.fetchall()}
    for column, definition in VIDEO_COLUMNS.items():
        if column not in existing:
            cursor.execute(f"ALTER TABLE videos ADD COLUMN {column} {definition}")


def init_local_dev() -> None:
    settings = get_settings()
    sqlite_path = settings.sqlite_path
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    video_path = settings.local_oss_root / DEMO_VIDEO_OBJECT_KEY
    if not video_path.is_file():
        raise FileNotFoundError(f"Missing demo video: {video_path}")

    connection = sqlite3.connect(sqlite_path)
    try:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            """
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
        )
        migrate_videos_table(cursor)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_episode_no ON videos (episode_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_series_episode ON videos (series_id, episode_no)")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS playback_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                client_time REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                server_time TEXT NOT NULL,
                extra_json TEXT NOT NULL,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_playback_events_video_time ON playback_events (video_id, server_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_playback_events_type ON playback_events (event_type)")
        cursor.execute(
            """
            INSERT INTO videos (
                video_id,
                series_id,
                series_name,
                title,
                episode_no,
                episode_label,
                duration,
                oss_bucket,
                oss_object_key,
                douyin_video_id,
                douyin_json_path,
                content_type,
                size,
                source,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local', 'active')
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                series_id = excluded.series_id,
                series_name = excluded.series_name,
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
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (
                DEMO_VIDEO_ID,
                "demo",
                "DramePulse Demo",
                DEMO_VIDEO_TITLE,
                1,
                "ep01",
                None,
                settings.local_oss_bucket,
                DEMO_VIDEO_OBJECT_KEY,
                None,
                None,
                "video/mp4",
                video_path.stat().st_size,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_local_dev()
    print(f"Initialized local dev database at {get_settings().sqlite_path}")

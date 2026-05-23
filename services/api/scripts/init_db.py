from __future__ import annotations

from services.api.config import get_settings, require_complete_cloud_settings
from services.api.db import connect_mysql


def init_db() -> None:
    settings = get_settings()
    require_complete_cloud_settings(settings)
    connection = connect_mysql(settings, with_database=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{settings.mysql_database}`")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    video_id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    episode_no INT NULL,
                    duration DOUBLE NULL,
                    oss_bucket VARCHAR(255) NOT NULL,
                    oss_object_key VARCHAR(512) NOT NULL,
                    content_type VARCHAR(128) NOT NULL DEFAULT 'video/mp4',
                    size BIGINT NOT NULL,
                    source VARCHAR(32) NOT NULL DEFAULT 'oss',
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    UNIQUE KEY uk_videos_oss_object (oss_bucket, oss_object_key),
                    KEY idx_videos_episode_no (episode_no),
                    KEY idx_videos_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS playback_events (
                    event_id VARCHAR(64) PRIMARY KEY,
                    event_type VARCHAR(64) NOT NULL,
                    user_id VARCHAR(128) NOT NULL,
                    video_id VARCHAR(64) NOT NULL,
                    client_time DOUBLE NOT NULL,
                    timestamp BIGINT NOT NULL,
                    server_time DATETIME(6) NOT NULL,
                    extra_json JSON NOT NULL,
                    KEY idx_playback_events_video_time (video_id, server_time),
                    KEY idx_playback_events_type (event_type),
                    CONSTRAINT fk_playback_events_video
                        FOREIGN KEY (video_id) REFERENCES videos(video_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")

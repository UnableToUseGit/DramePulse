from __future__ import annotations

from services.api.config import get_settings, require_complete_cloud_settings
from services.api.db import connect_mysql
from services.api.repositories.admin_analysis import create_analysis_table_mysql


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

VIDEO_INDEXES_MYSQL = {
    "uk_videos_oss_object": "CREATE UNIQUE INDEX uk_videos_oss_object ON videos (oss_bucket, oss_object_key)",
    "idx_videos_episode_no": "CREATE INDEX idx_videos_episode_no ON videos (episode_no)",
    "idx_videos_status": "CREATE INDEX idx_videos_status ON videos (status)",
    "idx_videos_series_episode": "CREATE INDEX idx_videos_series_episode ON videos (series_id, episode_no)",
}


def _existing_video_columns(cursor) -> set[str]:
    cursor.execute("SHOW COLUMNS FROM videos")
    return {str(row["Field"]) for row in cursor.fetchall()}


def _existing_video_indexes(cursor) -> set[str]:
    cursor.execute("SHOW INDEX FROM videos")
    return {str(row["Key_name"]) for row in cursor.fetchall()}


def migrate_videos_table(cursor) -> None:
    existing_columns = _existing_video_columns(cursor)
    for column, definition in VIDEO_COLUMNS_MYSQL.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE videos ADD COLUMN {column} {definition}")

    existing_indexes = _existing_video_indexes(cursor)
    for index_name, create_sql in VIDEO_INDEXES_MYSQL.items():
        if index_name not in existing_indexes:
            cursor.execute(create_sql)


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
            )
            migrate_videos_table(cursor)
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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS danmaku_items (
                    danmaku_id VARCHAR(64) PRIMARY KEY,
                    video_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(128) NULL,
                    client_time DOUBLE NOT NULL,
                    time_ms BIGINT NOT NULL,
                    text VARCHAR(512) NOT NULL,
                    source VARCHAR(32) NOT NULL DEFAULT 'user',
                    digg_count INT NOT NULL DEFAULT 0,
                    score DOUBLE NOT NULL DEFAULT 0,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    raw_json JSON NOT NULL,
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    KEY idx_danmaku_items_video_time (video_id, client_time),
                    CONSTRAINT fk_danmaku_items_video
                        FOREIGN KEY (video_id) REFERENCES videos(video_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_plans (
                    interaction_id VARCHAR(64) PRIMARY KEY,
                    highlight_id VARCHAR(64) NOT NULL,
                    video_id VARCHAR(64) NOT NULL,
                    trigger_time DOUBLE NOT NULL,
                    expire_time DOUBLE NOT NULL,
                    result_time DOUBLE NOT NULL,
                    interaction_type VARCHAR(64) NOT NULL,
                    question VARCHAR(512) NOT NULL,
                    feedback_json JSON NOT NULL,
                    display_position VARCHAR(64) NOT NULL DEFAULT 'subtitle_safe_area',
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    KEY idx_interaction_plans_video_status_time (video_id, status, trigger_time),
                    CONSTRAINT fk_interaction_plans_video
                        FOREIGN KEY (video_id) REFERENCES videos(video_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_options (
                    option_id VARCHAR(64) PRIMARY KEY,
                    interaction_id VARCHAR(64) NOT NULL,
                    text VARCHAR(255) NOT NULL,
                    danmaku_text VARCHAR(512) NOT NULL,
                    `rank` INT NOT NULL,
                    base_score DOUBLE NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    KEY idx_interaction_options_plan_rank (interaction_id, `rank`),
                    CONSTRAINT fk_interaction_options_plan
                        FOREIGN KEY (interaction_id) REFERENCES interaction_plans(interaction_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_events (
                    event_id VARCHAR(64) PRIMARY KEY,
                    event_type VARCHAR(64) NOT NULL,
                    user_id VARCHAR(128) NOT NULL,
                    video_id VARCHAR(64) NOT NULL,
                    highlight_id VARCHAR(64) NULL,
                    interaction_id VARCHAR(64) NULL,
                    option_id VARCHAR(64) NULL,
                    client_time DOUBLE NOT NULL,
                    timestamp BIGINT NOT NULL,
                    server_time DATETIME(6) NOT NULL,
                    extra_json JSON NOT NULL,
                    KEY idx_user_events_video_time (video_id, server_time),
                    KEY idx_user_events_interaction_type (interaction_id, event_type),
                    KEY idx_user_events_option (option_id),
                    CONSTRAINT fk_user_events_video
                        FOREIGN KEY (video_id) REFERENCES videos(video_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_option_stats (
                    interaction_id VARCHAR(64) NOT NULL,
                    option_id VARCHAR(64) NOT NULL,
                    vote_count INT NOT NULL DEFAULT 0,
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    PRIMARY KEY (interaction_id, option_id),
                    KEY idx_interaction_option_stats_plan (interaction_id),
                    CONSTRAINT fk_interaction_option_stats_option
                        FOREIGN KEY (option_id) REFERENCES interaction_options(option_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            create_analysis_table_mysql(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")

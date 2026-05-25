from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from services.api.config import get_settings


DEMO_VIDEO_ID = "demo_ep01"
DEMO_VIDEO_TITLE = "DramePulse Demo Episode 01"
DEMO_VIDEO_OBJECT_KEY = "demo_video.mp4"
DEMO_HIGHLIGHT_ID = "h_demo_ep01_001"
DEMO_INTERACTION_ID = "i_demo_ep01_001"


def seed_demo_data(cursor: sqlite3.Cursor) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    danmaku_path = repo_root / "apps" / "player-demo" / "src" / "fixtures" / "danmaku.json"
    if danmaku_path.is_file():
        payload = json.loads(danmaku_path.read_text(encoding="utf-8"))
        for item in payload.get("danmaku", [])[:80]:
            client_time = float(item.get("time_sec") or 0)
            cursor.execute(
                """
                INSERT INTO danmaku_items (
                    danmaku_id,
                    video_id,
                    user_id,
                    client_time,
                    time_ms,
                    text,
                    source,
                    digg_count,
                    score,
                    status,
                    raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'crawler', ?, ?, 'active', ?)
                ON CONFLICT(danmaku_id) DO UPDATE SET
                    client_time = excluded.client_time,
                    time_ms = excluded.time_ms,
                    text = excluded.text,
                    digg_count = excluded.digg_count,
                    score = excluded.score,
                    raw_json = excluded.raw_json
                """,
                (
                    str(item.get("danmaku_id")),
                    DEMO_VIDEO_ID,
                    item.get("user_id"),
                    client_time,
                    int(item.get("time_ms") or round(client_time * 1000)),
                    str(item.get("text") or ""),
                    int(item.get("digg_count") or 0),
                    float(item.get("score") or 0),
                    json.dumps(item.get("raw") or item, ensure_ascii=False),
                ),
            )

    feedback = {
        "type": "poll_result",
        "show_ratio": True,
        "show_resonance_text": True,
        "resonance_text_template": "你和 {ratio}% 的观众一样选择了「{option}」",
    }
    cursor.execute(
        """
        INSERT INTO interaction_plans (
            interaction_id,
            highlight_id,
            video_id,
            trigger_time,
            expire_time,
            result_time,
            interaction_type,
            question,
            feedback_json,
            display_position,
            status
        )
        VALUES (?, ?, ?, 8.96, 16.0, 18.0, 'danmaku_poll', ?, ?, 'subtitle_safe_area', 'active')
        ON CONFLICT(interaction_id) DO UPDATE SET
            trigger_time = excluded.trigger_time,
            expire_time = excluded.expire_time,
            result_time = excluded.result_time,
            question = excluded.question,
            feedback_json = excluded.feedback_json,
            display_position = excluded.display_position,
            status = excluded.status,
            updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
        """,
        (
            DEMO_INTERACTION_ID,
            DEMO_HIGHLIGHT_ID,
            DEMO_VIDEO_ID,
            "换你是女主你什么反应？",
            json.dumps(feedback, ensure_ascii=False),
        ),
    )
    options = [
        ("o_demo_ep01_001", "直接懵了", "我人直接傻了啊！", 1, 0.8),
        ("o_demo_ep01_002", "长得帅不亏", "男主这么帅血赚啊！", 2, 0.8),
        ("o_demo_ep01_003", "赶紧跑", "什么情况溜了溜了", 3, 0.8),
    ]
    for option in options:
        cursor.execute(
            """
            INSERT INTO interaction_options (
                option_id,
                interaction_id,
                text,
                danmaku_text,
                rank,
                base_score,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            ON CONFLICT(option_id) DO UPDATE SET
                text = excluded.text,
                danmaku_text = excluded.danmaku_text,
                rank = excluded.rank,
                base_score = excluded.base_score,
                status = excluded.status,
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (option[0], DEMO_INTERACTION_ID, option[1], option[2], option[3], option[4]),
        )


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
                title TEXT NOT NULL,
                episode_no INTEGER NULL,
                duration REAL NULL,
                oss_bucket TEXT NOT NULL,
                oss_object_key TEXT NOT NULL,
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_episode_no ON videos (episode_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos (status)")
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
            CREATE TABLE IF NOT EXISTS danmaku_items (
                danmaku_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                user_id TEXT NULL,
                client_time REAL NOT NULL,
                time_ms INTEGER NOT NULL,
                text TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'user',
                digg_count INTEGER NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                raw_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_danmaku_items_video_time ON danmaku_items (video_id, client_time)")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_plans (
                interaction_id TEXT PRIMARY KEY,
                highlight_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                trigger_time REAL NOT NULL,
                expire_time REAL NOT NULL,
                result_time REAL NOT NULL,
                interaction_type TEXT NOT NULL,
                question TEXT NOT NULL,
                feedback_json TEXT NOT NULL,
                display_position TEXT NOT NULL DEFAULT 'subtitle_safe_area',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_interaction_plans_video_status_time ON interaction_plans (video_id, status, trigger_time)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_options (
                option_id TEXT PRIMARY KEY,
                interaction_id TEXT NOT NULL,
                text TEXT NOT NULL,
                danmaku_text TEXT NOT NULL,
                rank INTEGER NOT NULL,
                base_score REAL NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                FOREIGN KEY (interaction_id) REFERENCES interaction_plans(interaction_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interaction_options_plan_rank ON interaction_options (interaction_id, rank)")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                highlight_id TEXT NULL,
                interaction_id TEXT NULL,
                option_id TEXT NULL,
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_events_video_time ON user_events (video_id, server_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_events_interaction_type ON user_events (interaction_id, event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_events_option ON user_events (option_id)")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_option_stats (
                interaction_id TEXT NOT NULL,
                option_id TEXT NOT NULL,
                vote_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                PRIMARY KEY (interaction_id, option_id),
                FOREIGN KEY (option_id) REFERENCES interaction_options(option_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interaction_option_stats_plan ON interaction_option_stats (interaction_id)")
        cursor.execute(
            """
            INSERT INTO videos (
                video_id,
                title,
                episode_no,
                duration,
                oss_bucket,
                oss_object_key,
                content_type,
                size,
                source,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'local', 'active')
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                episode_no = excluded.episode_no,
                duration = excluded.duration,
                oss_bucket = excluded.oss_bucket,
                oss_object_key = excluded.oss_object_key,
                content_type = excluded.content_type,
                size = excluded.size,
                source = excluded.source,
                status = excluded.status,
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            """,
            (
                DEMO_VIDEO_ID,
                DEMO_VIDEO_TITLE,
                1,
                None,
                settings.local_oss_bucket,
                DEMO_VIDEO_OBJECT_KEY,
                "video/mp4",
                video_path.stat().st_size,
            ),
        )
        seed_demo_data(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_local_dev()
    print(f"Initialized local dev database at {get_settings().sqlite_path}")

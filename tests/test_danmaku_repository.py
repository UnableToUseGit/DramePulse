from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.api.repositories import danmaku


class DanmakuRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.data_root = self.tmp_path / "VideoData"
        self.data_root.mkdir()
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.data_root)
        os.environ["LOCAL_OSS_BUCKET"] = "local"

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def create_videos_table(self, *, douyin_json_path: str | None) -> None:
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.execute(
                """
                CREATE TABLE videos (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    episode_no INTEGER NULL,
                    duration REAL NULL,
                    oss_bucket TEXT NOT NULL,
                    oss_object_key TEXT NOT NULL,
                    douyin_json_path TEXT NULL,
                    content_type TEXT NOT NULL DEFAULT 'video/mp4',
                    size INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'local',
                    status TEXT NOT NULL DEFAULT 'active'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, title, episode_no, duration, oss_bucket,
                    oss_object_key, douyin_json_path, content_type, size, source, status
                )
                VALUES (?, 'Episode 1', 1, 10.0, 'local', 'raw/demo/ep01/video.mp4', ?, 'video/mp4', 10, 'local', 'active')
                """,
                ("demo_ep01", douyin_json_path),
            )
            connection.commit()
        finally:
            connection.close()

    def create_danmaku_table(self) -> None:
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.execute(
                """
                CREATE TABLE danmaku_items (
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
                    created_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def insert_persisted_danmaku(self) -> None:
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.executemany(
                """
                INSERT INTO danmaku_items (
                    danmaku_id, video_id, user_id, client_time, time_ms, text,
                    source, digg_count, score, status, raw_json, created_at
                )
                VALUES (?, 'demo_ep01', NULL, ?, ?, ?, 'douyin', ?, ?, 'active', '{}', '')
                """,
                [
                    ("persisted_2", 2.0, 2000, "second persisted", 3, 1.5),
                    ("persisted_1", 1.0, 1000, "first persisted", 8, 9.5),
                ],
            )
            connection.commit()
        finally:
            connection.close()

    def insert_many_persisted_danmaku(self, count: int = 150) -> None:
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.executemany(
                """
                INSERT INTO danmaku_items (
                    danmaku_id, video_id, user_id, client_time, time_ms, text,
                    source, digg_count, score, status, raw_json, created_at
                )
                VALUES (?, 'demo_ep01', NULL, ?, ?, ?, 'douyin', ?, ?, 'active', '{}', '')
                """,
                [
                    (
                        f"persisted_{index:03d}",
                        float(index),
                        index * 1000,
                        f"persisted text {index}",
                        index % 50,
                        float(index % 30),
                    )
                    for index in range(count)
                ],
            )
            connection.commit()
        finally:
            connection.close()

    def write_douyin_json(self) -> str:
        json_path = self.data_root / "raw" / "demo" / "ep01" / "douyin.json"
        json_path.parent.mkdir(parents=True)
        json_path.write_text(
            json.dumps(
                {
                    "danmaku": {
                        "count": 2,
                        "items": [
                            {
                                "danmaku_id": "d2",
                                "time_sec": 2.0,
                                "text": "second raw",
                                "digg_count": 3,
                                "score": 1.5,
                                "raw": {"large": "payload"},
                            },
                            {
                                "danmaku_id": "d1",
                                "time_sec": 1.0,
                                "text": "first raw",
                                "digg_count": 8,
                                "score": 9.5,
                            },
                        ],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "raw/demo/ep01/douyin.json"

    def test_get_video_danmaku_returns_sorted_lightweight_items(self) -> None:
        relative_path = self.write_douyin_json()
        self.create_videos_table(douyin_json_path=relative_path)

        payload = danmaku.get_video_danmaku("demo_ep01")

        self.assertEqual(payload["video_id"], "demo_ep01")
        self.assertTrue(payload["available"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            payload["items"],
            [
                {
                    "danmaku_id": "d1",
                    "time_sec": 1.0,
                    "text": "first raw",
                    "digg_count": 8,
                    "score": 9.5,
                },
                {
                    "danmaku_id": "d2",
                    "time_sec": 2.0,
                    "text": "second raw",
                    "digg_count": 3,
                    "score": 1.5,
                },
            ],
        )

    def test_get_video_danmaku_prefers_persisted_items(self) -> None:
        self.create_videos_table(douyin_json_path="raw/demo/ep01/missing.json")
        self.create_danmaku_table()
        self.insert_persisted_danmaku()

        payload = danmaku.get_video_danmaku("demo_ep01")

        self.assertEqual(payload["video_id"], "demo_ep01")
        self.assertTrue(payload["available"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            payload["items"],
            [
                {
                    "danmaku_id": "persisted_1",
                    "time_sec": 1.0,
                    "text": "first persisted",
                    "digg_count": 8,
                    "score": 9.5,
                },
                {
                    "danmaku_id": "persisted_2",
                    "time_sec": 2.0,
                    "text": "second persisted",
                    "digg_count": 3,
                    "score": 1.5,
                },
            ],
        )

    def test_get_video_danmaku_limits_persisted_items_by_default(self) -> None:
        self.create_videos_table(douyin_json_path="raw/demo/ep01/missing.json")
        self.create_danmaku_table()
        self.insert_many_persisted_danmaku()

        payload = danmaku.get_video_danmaku("demo_ep01")

        self.assertEqual(payload["count"], 150)
        self.assertLessEqual(len(payload["items"]), 120)
        self.assertLessEqual(len(payload["danmaku"]), 120)
        times = [item["client_time"] for item in payload["danmaku"]]
        self.assertEqual(times, sorted(times))

    def test_get_video_danmaku_honors_limit(self) -> None:
        self.create_videos_table(douyin_json_path="raw/demo/ep01/missing.json")
        self.create_danmaku_table()
        self.insert_many_persisted_danmaku()

        payload = danmaku.get_video_danmaku("demo_ep01", limit=20)

        self.assertEqual(payload["count"], 150)
        self.assertLessEqual(len(payload["items"]), 20)
        self.assertLessEqual(len(payload["danmaku"]), 20)

    def test_get_video_danmaku_filters_time_window_before_limit(self) -> None:
        self.create_videos_table(douyin_json_path="raw/demo/ep01/missing.json")
        self.create_danmaku_table()
        self.insert_many_persisted_danmaku()

        payload = danmaku.get_video_danmaku("demo_ep01", from_time=10, to_time=19, limit=5)

        self.assertEqual(payload["count"], 10)
        self.assertLessEqual(len(payload["items"]), 5)
        self.assertTrue(all(10 <= item["time_sec"] <= 19 for item in payload["items"]))

    def test_get_video_danmaku_returns_unavailable_when_path_is_null(self) -> None:
        self.create_videos_table(douyin_json_path=None)

        payload = danmaku.get_video_danmaku("demo_ep01")

        self.assertEqual(
            payload,
            {"video_id": "demo_ep01", "available": False, "count": 0, "items": [], "danmaku": []},
        )

    def test_get_video_danmaku_returns_none_for_missing_video(self) -> None:
        self.create_videos_table(douyin_json_path=None)

        self.assertIsNone(danmaku.get_video_danmaku("missing"))


if __name__ == "__main__":
    unittest.main()

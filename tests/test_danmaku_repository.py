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
                VALUES (?, '第1集', 1, 10.0, 'local', 'raw/demo/ep01/video.mp4', ?, 'video/mp4', 10, 'local', 'active')
                """,
                ("demo_ep01", douyin_json_path),
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
                                "text": "第二条",
                                "digg_count": 3,
                                "score": 1.5,
                                "raw": {"large": "payload"},
                            },
                            {
                                "danmaku_id": "d1",
                                "time_sec": 1.0,
                                "text": "第一条",
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
                    "text": "第一条",
                    "digg_count": 8,
                    "score": 9.5,
                },
                {
                    "danmaku_id": "d2",
                    "time_sec": 2.0,
                    "text": "第二条",
                    "digg_count": 3,
                    "score": 1.5,
                },
            ],
        )

    def test_get_video_danmaku_returns_unavailable_when_path_is_null(self) -> None:
        self.create_videos_table(douyin_json_path=None)

        payload = danmaku.get_video_danmaku("demo_ep01")

        self.assertEqual(payload, {"video_id": "demo_ep01", "available": False, "count": 0, "items": []})

    def test_get_video_danmaku_returns_none_for_missing_video(self) -> None:
        self.create_videos_table(douyin_json_path=None)

        self.assertIsNone(danmaku.get_video_danmaku("missing"))


if __name__ == "__main__":
    unittest.main()

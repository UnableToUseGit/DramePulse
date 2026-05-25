from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.api.scripts import import_video_manifest
from services.api.scripts.init_local_dev import init_local_dev


class ImportVideoManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.tmp_path / "VideoData")
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        (self.tmp_path / "VideoData" / "raw" / "beipai_xunbao_biji" / "ep63").mkdir(parents=True)
        (self.tmp_path / "VideoData" / "raw" / "beipai_xunbao_biji" / "ep63" / "video.mp4").write_bytes(
            b"fake video"
        )

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def write_manifest(self) -> Path:
        (self.tmp_path / "VideoData" / "raw" / "beipai_xunbao_biji" / "ep63" / "douyin.json").write_text(
            "{}",
            encoding="utf-8",
        )
        manifest_path = self.tmp_path / "VideoData" / "video_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "video_manifest.v1",
                    "generated_at": "2026-05-24T18:00:00+08:00",
                    "videos": [
                        {
                            "video_id": "beipai_xunbao_biji_ep63",
                            "series_id": "beipai_xunbao_biji",
                            "series_name": "北派寻宝笔记",
                            "episode_no": 63,
                            "episode_label": "ep63",
                            "title": "北派寻宝笔记 第63集",
                            "duration": 123.45,
                            "source": "local",
                            "status": "active",
                            "storage": {
                                "bucket": "local",
                                "object_key": "raw/beipai_xunbao_biji/ep63/video.mp4",
                                "content_type": "video/mp4",
                                "size": 10,
                            },
                            "douyin": {
                                "video_id": "7622167244545609002",
                                "video_url": "https://www.douyin.com/video/7622167244545609002",
                                "json_path": "raw/beipai_xunbao_biji/ep63/douyin.json",
                                "danmaku_count": 2,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return manifest_path

    def test_ensure_video_schema_creates_new_columns(self) -> None:
        import_video_manifest.ensure_video_schema()

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(videos)").fetchall()}
        finally:
            connection.close()

        self.assertIn("series_id", columns)
        self.assertIn("series_name", columns)
        self.assertIn("episode_label", columns)
        self.assertIn("douyin_video_id", columns)
        self.assertIn("douyin_json_path", columns)

    def test_ensure_video_schema_migrates_existing_videos_table(self) -> None:
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
                    content_type TEXT NOT NULL DEFAULT 'video/mp4',
                    size INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'local',
                    status TEXT NOT NULL DEFAULT 'active'
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        import_video_manifest.ensure_video_schema()

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(videos)").fetchall()}
        finally:
            connection.close()

        self.assertIn("series_id", columns)
        self.assertIn("series_name", columns)
        self.assertIn("episode_label", columns)
        self.assertIn("douyin_video_id", columns)
        self.assertIn("douyin_json_path", columns)

    def test_import_video_manifest_upserts_video_row(self) -> None:
        manifest_path = self.write_manifest()

        imported = import_video_manifest.import_video_manifest(
            manifest_path,
            data_root=self.tmp_path / "VideoData",
        )

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute("SELECT * FROM videos").fetchone()
        finally:
            connection.close()

        self.assertEqual(imported, 1)
        self.assertEqual(row["video_id"], "beipai_xunbao_biji_ep63")
        self.assertEqual(row["series_id"], "beipai_xunbao_biji")
        self.assertEqual(row["series_name"], "北派寻宝笔记")
        self.assertEqual(row["episode_label"], "ep63")
        self.assertEqual(row["douyin_video_id"], "7622167244545609002")
        self.assertEqual(row["douyin_json_path"], "raw/beipai_xunbao_biji/ep63/douyin.json")

    def test_import_video_manifest_requires_existing_video_under_data_root(self) -> None:
        manifest_path = self.write_manifest()
        (self.tmp_path / "VideoData" / "raw" / "beipai_xunbao_biji" / "ep63" / "video.mp4").unlink()

        with self.assertRaisesRegex(FileNotFoundError, "video file"):
            import_video_manifest.import_video_manifest(
                manifest_path,
                data_root=self.tmp_path / "VideoData",
            )

    def test_import_video_manifest_requires_existing_douyin_json_when_available(self) -> None:
        manifest_path = self.write_manifest()
        (self.tmp_path / "VideoData" / "raw" / "beipai_xunbao_biji" / "ep63" / "douyin.json").unlink()

        with self.assertRaisesRegex(FileNotFoundError, "douyin json"):
            import_video_manifest.import_video_manifest(
                manifest_path,
                data_root=self.tmp_path / "VideoData",
            )

    def test_import_video_manifest_allows_missing_douyin_json_when_unavailable(self) -> None:
        manifest_path = self.write_manifest()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["videos"][0]["douyin"]["available"] = False
        payload["videos"][0]["douyin"]["video_id"] = None
        payload["videos"][0]["douyin"]["video_url"] = None
        payload["videos"][0]["douyin"]["json_path"] = None
        payload["videos"][0]["douyin"]["danmaku_count"] = 0
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (self.tmp_path / "VideoData" / "raw" / "beipai_xunbao_biji" / "ep63" / "douyin.json").unlink()

        imported = import_video_manifest.import_video_manifest(
            manifest_path,
            data_root=self.tmp_path / "VideoData",
        )

        self.assertEqual(imported, 1)

    def test_init_local_dev_migrates_existing_videos_table(self) -> None:
        (self.tmp_path / "VideoData" / "demo_video.mp4").write_bytes(b"fake demo video")
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
                    content_type TEXT NOT NULL DEFAULT 'video/mp4',
                    size INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'local',
                    status TEXT NOT NULL DEFAULT 'active',
                    UNIQUE (oss_bucket, oss_object_key)
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        init_local_dev()

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute("SELECT * FROM videos WHERE video_id = 'demo_ep01'").fetchone()
        finally:
            connection.close()

        self.assertEqual(row["series_id"], "demo")
        self.assertEqual(row["series_name"], "DramePulse Demo")
        self.assertEqual(row["episode_label"], "ep01")


if __name__ == "__main__":
    unittest.main()

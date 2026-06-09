from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.main import create_app


class VideoRepositoryStoryAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.previous_env = {
            name: os.environ.get(name)
            for name in [
                "DRAMEPULSE_MODE",
                "SQLITE_PATH",
                "LOCAL_OSS_ROOT",
                "LOCAL_OSS_BUCKET",
                "CDN_BASE_URL",
            ]
        }
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.root / "dramepulse.sqlite")

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_storyboard_endpoint_returns_generated_sheet_urls(self) -> None:
        self._insert_storyboard(
            "ep_08",
            {
                "sheets": [{"url": "sheet_000.jpg", "start_time": 0, "frame_count": 25}],
            },
        )

        client = TestClient(create_app())
        response = client.get("/api/videos/ep_08/storyboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["available"], True)
        self.assertEqual(response.json()["sheets"][0]["url"], "sheet_000.jpg")

    def test_legacy_storyboard_route_reads_public_asset_storage(self) -> None:
        storyboard_dir = self.root / "storyboards" / "ep_08"
        storyboard_dir.mkdir(parents=True)
        (storyboard_dir / "sheet_000.jpg").write_bytes(b"jpeg")

        client = TestClient(create_app())
        response = client.get("/storyboards/ep_08/sheet_000.jpg")

        self.assertEqual(response.status_code, 404)

    def _insert_storyboard(self, video_id: str, manifest: dict[str, object]) -> None:
        connection = sqlite3.connect(os.environ["SQLITE_PATH"])
        try:
            connection.execute(
                """
                CREATE TABLE videos (
                    video_id TEXT PRIMARY KEY,
                    series_id TEXT NULL,
                    series_name TEXT NULL,
                    title TEXT NOT NULL,
                    episode_no INTEGER NULL,
                    episode_label TEXT NULL,
                    duration REAL NULL,
                    oss_object_key TEXT NULL,
                    source TEXT NULL,
                    douyin_video_id TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO videos (
                    video_id,
                    series_id,
                    series_name,
                    title,
                    episode_no,
                    episode_label,
                    duration,
                    oss_object_key,
                    source,
                    douyin_video_id,
                    status
                )
                VALUES (?, 'demo', 'Demo', 'Episode 8', 8, 'ep08', 120, 'videos/ep_08.mp4', 'oss', NULL, 'active')
                """,
                (video_id,),
            )
            connection.execute(
                """
                CREATE TABLE video_storyboards (
                    video_id TEXT PRIMARY KEY,
                    interval_seconds REAL NOT NULL,
                    frame_width INTEGER NOT NULL,
                    frame_height INTEGER NOT NULL,
                    columns_count INTEGER NOT NULL,
                    rows_count INTEGER NOT NULL,
                    manifest_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO video_storyboards (
                    video_id,
                    interval_seconds,
                    frame_width,
                    frame_height,
                    columns_count,
                    rows_count,
                    manifest_json,
                    status
                )
                VALUES (?, 1, 160, 90, 5, 5, ?, 'active')
                """,
                (video_id, json.dumps(manifest)),
            )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()

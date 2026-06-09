from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.api.scripts import backfill_video_durations


class BackfillVideoDurationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.tmp_path / "oss")
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        (self.tmp_path / "oss" / "dramas" / "demo" / "episodes" / "ep01").mkdir(parents=True)
        (self.tmp_path / "oss" / "dramas" / "demo" / "episodes" / "ep01" / "video.mp4").write_bytes(b"video")
        self._create_videos_table()

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def _create_videos_table(self) -> None:
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.execute(
                """
                CREATE TABLE videos (
                    video_id TEXT PRIMARY KEY,
                    series_id TEXT NULL,
                    title TEXT NOT NULL,
                    episode_no INTEGER NULL,
                    duration REAL NULL,
                    oss_bucket TEXT NOT NULL,
                    oss_object_key TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'video/mp4',
                    size INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'local',
                    status TEXT NOT NULL DEFAULT 'active',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, title, episode_no, duration,
                    oss_bucket, oss_object_key, content_type, size, source, status
                )
                VALUES (?, ?, ?, ?, NULL, ?, ?, 'video/mp4', ?, 'oss', 'active')
                """,
                (
                    "demo_ep01",
                    "demo",
                    "Demo ep01",
                    1,
                    "local",
                    "dramas/demo/episodes/ep01/video.mp4",
                    len(b"video"),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_dry_run_does_not_update_duration(self) -> None:
        with patch.object(backfill_video_durations, "probe_duration_seconds", return_value=12.345):
            summary = backfill_video_durations.backfill_video_durations(
                apply=False,
                video_ids=[],
                include_existing=False,
                limit=None,
                ffprobe_bin="ffprobe",
            )

        self.assertEqual(summary["matched"], 1)
        self.assertEqual(summary["results"][0]["new_duration"], 12.345)
        self.assertEqual(summary["results"][0]["status"], "dry_run")
        self.assertIsNone(self._duration())

    def test_apply_updates_duration(self) -> None:
        with patch.object(backfill_video_durations, "probe_duration_seconds", return_value=12.345):
            summary = backfill_video_durations.backfill_video_durations(
                apply=True,
                video_ids=[],
                include_existing=False,
                limit=None,
                ffprobe_bin="ffprobe",
            )

        self.assertEqual(summary["matched"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(self._duration(), 12.345)

    def _duration(self) -> float | None:
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            row = connection.execute("SELECT duration FROM videos WHERE video_id = 'demo_ep01'").fetchone()
            return row[0]
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()

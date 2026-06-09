from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.scripts.import_story_chapters import import_story_chapters
from services.api.scripts.init_local_dev import init_local_dev


class StoryChapterImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        shutil.copyfile(Path("apps/player-demo/assets/video/ep01.mp4"), self.tmp_path / "demo_video.mp4")
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        init_local_dev()
        self.sqlite_path = self.tmp_path / "dramepulse.sqlite"
        self._insert_video("naniandonzhi_ep01", "naniandonzhi", 1)
        self._insert_video("naniandonzhi_ep04", "naniandonzhi", 4)

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_import_matches_alias_and_exposes_api_assets(self) -> None:
        source_root = self.tmp_path / "story_chapter"
        self._write_story_chapter_dir(source_root / "nanian_dongzhi_ep01", "nanian_dongzhi_ep01", 1)
        self._write_story_chapter_dir(source_root / "naniandongzhi_ep04", "naniandongzhi_ep04", 4)

        dry_run = import_story_chapters(source_root, apply=False)
        self.assertEqual(dry_run["matched"], 2)
        self.assertEqual(dry_run["applied"], 0)

        applied = import_story_chapters(source_root, apply=True)
        self.assertEqual(applied["applied"], 2)
        self.assertEqual(applied["matched"], 2)

        connection = sqlite3.connect(self.sqlite_path)
        try:
            rows = connection.execute(
                "SELECT video_id, source_video_id, canonical_series_id FROM video_story_chapter_assets ORDER BY video_id"
            ).fetchall()
            chapters = connection.execute(
                "SELECT video_id, chapter_index, title FROM story_chapters WHERE status = 'active' ORDER BY video_id"
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual(
            {row[0]: (row[1], row[2]) for row in rows},
            {
                "naniandonzhi_ep04": ("naniandongzhi_ep04", "naniandonzhi"),
                "naniandonzhi_ep01": ("nanian_dongzhi_ep01", "naniandonzhi"),
            },
        )
        self.assertEqual(len(chapters), 2)

        client = TestClient(create_app())
        response = client.get("/api/videos/naniandonzhi_ep04/story-chapters")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["source_video_id"], "naniandongzhi_ep04")
        self.assertEqual(payload["canonical_series_id"], "naniandonzhi")
        self.assertEqual(payload["chapters"][0]["title"], "第4集章节")

        raw_response = client.get("/api/videos/naniandonzhi_ep04/story-chapters/raw")
        self.assertEqual(raw_response.status_code, 200)
        self.assertIn('"video_id": "naniandongzhi_ep04"', raw_response.json()["content"])

        debug_response = client.get("/api/videos/naniandonzhi_ep04/story-chapters/debug")
        self.assertEqual(debug_response.status_code, 200)
        self.assertEqual(debug_response.json()["filename"], "story_chapters.debug.json")

        assets_response = client.get("/api/videos/naniandonzhi_ep04/playback-assets")
        self.assertEqual(assets_response.status_code, 200)
        self.assertEqual(assets_response.json()["story_chapters"][0]["title"], "第4集章节")

    def _insert_video(self, video_id: str, series_id: str, episode_no: int) -> None:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    oss_bucket, oss_object_key, content_type, size, source, status
                )
                VALUES (?, ?, '那年冬至', ?, ?, ?, 'local', ?, 'video/mp4', 1024, 'local', 'active')
                """,
                (video_id, series_id, f"那年冬至 第{episode_no}集", episode_no, f"ep{episode_no:02d}", f"{video_id}.mp4"),
            )
            connection.commit()
        finally:
            connection.close()

    def _write_story_chapter_dir(self, path: Path, source_video_id: str, episode_no: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        payload = {
            "video_id": source_video_id,
            "series_id": "naniandongzhi" if episode_no == 4 else "nanian_dongzhi",
            "story_chapters": [
                {
                    "chapter_id": f"ch_{source_video_id}_001",
                    "start_time": 0.0,
                    "end_time": 12.5,
                    "title": f"第{episode_no}集章节",
                    "summary": "章节摘要",
                    "reason": "切分原因",
                }
            ],
        }
        (path / "story_chapters.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (path / "story_chapters.debug.json").write_text(
            json.dumps({**payload, "debug": {"segments": []}}, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()

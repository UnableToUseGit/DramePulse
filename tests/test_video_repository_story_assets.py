from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.repositories import videos


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
                "STORY_CHAPTER_OUTPUT_ROOT",
                "STORYBOARD_ROOT",
            ]
        }
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["STORY_CHAPTER_OUTPUT_ROOT"] = str(self.root / "chapter_output")
        os.environ["STORYBOARD_ROOT"] = str(self.root / "storyboards")
        self.row = {
            "video_id": "ep_08",
            "series_id": "demo",
            "series_name": "Demo",
            "title": "第8集",
            "episode_no": 8,
            "episode_label": "ep08",
            "duration": 120.0,
            "oss_bucket": "dramepulse",
            "oss_object_key": "短剧合集/第8集.mp4",
            "douyin_video_id": "123",
            "source": "oss",
        }

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_video_response_includes_local_story_assets_when_present(self) -> None:
        chapter_dir = self.root / "chapter_output" / "ep_08"
        storyboard_dir = self.root / "storyboards" / "ep_08"
        chapter_dir.mkdir(parents=True)
        storyboard_dir.mkdir(parents=True)
        (chapter_dir / "story_chapters.json").write_text(
            json.dumps(
                {
                    "story_chapters": [
                        {
                            "chapter_id": "ch_ep_08_001",
                            "video_id": "ep_08",
                            "start_time": 0,
                            "end_time": 12,
                            "title": "债主堵门",
                            "summary": "债主上门逼债。",
                            "importance": 0.7,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (storyboard_dir / "storyboard_manifest.json").write_text(
            json.dumps(
                {
                    "video_id": "ep_08",
                    "interval_seconds": 1,
                    "frame_width": 160,
                    "frame_height": 90,
                    "columns": 5,
                    "rows": 5,
                    "sheets": [{"url": "sheet_000.jpg", "start_time": 0, "frame_count": 25}],
                }
            ),
            encoding="utf-8",
        )

        video = videos._to_video_response(self.row)

        self.assertEqual(video["story_chapters"][0]["title"], "债主堵门")
        self.assertEqual(video["storyboard"]["sheets"][0]["url"], "/storyboards/ep_08/sheet_000.jpg")

    def test_storyboard_static_mount_serves_generated_sheets(self) -> None:
        storyboard_dir = self.root / "storyboards" / "ep_08"
        storyboard_dir.mkdir(parents=True)
        (storyboard_dir / "sheet_000.jpg").write_bytes(b"jpeg")

        client = TestClient(create_app())
        response = client.get("/storyboards/ep_08/sheet_000.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"jpeg")


if __name__ == "__main__":
    unittest.main()

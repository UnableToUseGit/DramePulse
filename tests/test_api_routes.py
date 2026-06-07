from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.scripts.init_local_dev import init_local_dev


class ApiRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "dramepulse-api"})

    def test_list_videos(self) -> None:
        with patch("services.api.routers.videos.list_active_videos") as list_active_videos:
            list_active_videos.return_value = [
                {
                    "video_id": "ep_10",
                    "series_id": "demo",
                    "series_name": "测试短剧",
                    "title": "第10集",
                    "episode_no": 10,
                    "episode_label": "ep10",
                    "duration": None,
                    "stream_url": "/api/videos/ep_10/stream",
                    "danmaku_url": "/api/videos/ep_10/danmaku",
                    "source": "oss",
                    "douyin_video_id": "123456",
                }
            ]
            response = self.client.get("/api/videos")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"][0]["video_id"], "ep_10")
        self.assertEqual(response.json()["videos"][0]["series_name"], "测试短剧")
        self.assertEqual(response.json()["videos"][0]["episode_label"], "ep10")
        self.assertEqual(response.json()["videos"][0]["douyin_video_id"], "123456")
        self.assertEqual(response.json()["videos"][0]["stream_url"], "/api/videos/ep_10/stream")
        self.assertEqual(response.json()["videos"][0]["danmaku_url"], "/api/videos/ep_10/danmaku")

    def test_home_feed_returns_first_episode_per_series(self) -> None:
        with patch("services.api.routers.feed.list_home_feed_videos") as list_home_feed_videos:
            list_home_feed_videos.return_value = [
                {
                    "video_id": "demo_ep01",
                    "series_id": "demo",
                    "series_name": "Demo",
                    "title": "Demo ep01",
                    "episode_no": 1,
                    "episode_label": "ep01",
                    "duration": 126.5,
                    "stream_url": "/api/videos/demo_ep01/stream",
                    "danmaku_url": "/api/videos/demo_ep01/danmaku",
                    "source": "oss",
                    "douyin_video_id": None,
                }
            ]
            response = self.client.get("/api/feed/home")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"][0]["video_id"], "demo_ep01")
        self.assertEqual(response.json()["videos"][0]["episode_no"], 1)

    def test_series_list(self) -> None:
        with patch("services.api.routers.series.list_series") as list_series:
            list_series.return_value = [
                {
                    "series_id": "demo",
                    "title": "Demo",
                    "cover_url": "/api/admin/series/demo/cover",
                    "summary": None,
                    "episode_count": 5,
                    "first_video_id": "demo_ep01",
                    "status": "active",
                }
            ]
            response = self.client.get("/api/series")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["series"][0]["series_id"], "demo")
        self.assertEqual(response.json()["series"][0]["episode_count"], 5)
        self.assertEqual(response.json()["series"][0]["first_video_id"], "demo_ep01")

    def test_series_episodes(self) -> None:
        with patch("services.api.routers.series.list_series_episodes") as list_series_episodes:
            list_series_episodes.return_value = {
                "series_id": "demo",
                "series_name": "Demo",
                "episodes": [
                    {
                        "video_id": "demo_ep01",
                        "series_id": "demo",
                        "series_name": "Demo",
                        "title": "Demo ep01",
                        "episode_no": 1,
                        "episode_label": "ep01",
                        "duration": 126.5,
                        "stream_url": "/api/videos/demo_ep01/stream",
                        "danmaku_url": "/api/videos/demo_ep01/danmaku",
                        "source": "oss",
                        "douyin_video_id": None,
                    }
                ],
            }
            response = self.client.get("/api/series/demo/episodes")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["series_id"], "demo")
        self.assertEqual(response.json()["episodes"][0]["video_id"], "demo_ep01")

    def test_series_episode_not_found(self) -> None:
        with patch("services.api.routers.series.get_series_episode", return_value=None):
            response = self.client.get("/api/series/demo/episodes/99")

        self.assertEqual(response.status_code, 404)

    def test_get_video_not_found(self) -> None:
        with patch("services.api.routers.videos.get_video", return_value=None):
            response = self.client.get("/api/videos/missing")

        self.assertEqual(response.status_code, 404)

    def test_stream_video_with_range(self) -> None:
        with (
            patch("services.api.routers.videos.get_video_storage") as get_video_storage,
            patch("services.api.routers.videos.read_object_range") as read_object_range,
        ):
            get_video_storage.return_value = {
                "video_id": "ep_10",
                "oss_bucket": "dramepulse",
                "oss_object_key": "第10集.mp4",
                "content_type": "video/mp4",
                "size": 10_000,
            }
            read_object_range.return_value = b"abcd"
            response = self.client.get("/api/videos/ep_10/stream", headers={"Range": "bytes=0-3"})

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"abcd")
        self.assertEqual(response.headers["content-type"], "video/mp4")
        self.assertEqual(response.headers["content-disposition"], "inline")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["content-range"], "bytes 0-3/10000")
        read_object_range.assert_called_once_with("第10集.mp4", 0, 3, bucket_name="dramepulse")

    def test_get_video_danmaku(self) -> None:
        with patch("services.api.routers.videos.get_video_danmaku") as get_video_danmaku:
            get_video_danmaku.return_value = {
                "video_id": "ep_10",
                "available": True,
                "count": 1,
                "items": [
                    {
                        "danmaku_id": "d1",
                        "time_sec": 1.2,
                        "text": "太爽了",
                        "digg_count": 8,
                        "score": 9.5,
                    }
                ],
            }

            response = self.client.get("/api/videos/ep_10/danmaku")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_id"], "ep_10")
        self.assertEqual(response.json()["available"], True)
        self.assertEqual(response.json()["items"][0]["text"], "太爽了")

    def test_get_video_danmaku_not_found(self) -> None:
        with patch("services.api.routers.videos.get_video_danmaku", return_value=None):
            response = self.client.get("/api/videos/missing/danmaku")

        self.assertEqual(response.status_code, 404)

    def test_get_video_playback_assets(self) -> None:
        with patch("services.api.routers.videos.get_video_playback_assets") as get_video_playback_assets:
            get_video_playback_assets.return_value = {
                "video": {
                    "video_id": "ep_10",
                    "series_id": "demo",
                    "series_name": "Demo",
                    "title": "Demo ep10",
                    "episode_no": 10,
                    "episode_label": "ep10",
                    "duration": 120,
                    "stream_url": "/api/videos/ep_10/stream",
                    "danmaku_url": "/api/videos/ep_10/danmaku",
                    "source": "oss",
                    "douyin_video_id": None,
                },
                "danmaku": {
                    "video_id": "ep_10",
                    "available": False,
                    "count": 0,
                    "items": [],
                    "danmaku": [],
                },
                "storyboard": {
                    "video_id": "ep_10",
                    "available": False,
                    "interval_seconds": None,
                    "frame_width": None,
                    "frame_height": None,
                    "columns": None,
                    "rows": None,
                    "sheets": [],
                },
                "story_chapters": [],
                "interaction_plans": [],
            }
            response = self.client.get("/api/videos/ep_10/playback-assets")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video"]["video_id"], "ep_10")
        self.assertEqual(response.json()["danmaku"]["available"], False)
        self.assertEqual(response.json()["storyboard"]["available"], False)
        self.assertEqual(response.json()["interaction_plans"], [])

    def test_get_video_storyboard(self) -> None:
        with (
            patch("services.api.routers.videos.get_video") as get_video,
            patch("services.api.routers.videos.get_video_storyboard") as get_video_storyboard,
        ):
            get_video.return_value = {
                "video_id": "ep_10",
                "series_id": "demo",
                "series_name": "Demo",
                "title": "Demo ep10",
                "episode_no": 10,
                "episode_label": "ep10",
                "duration": 120,
                "stream_url": "/api/videos/ep_10/stream",
                "danmaku_url": "/api/videos/ep_10/danmaku",
                "source": "oss",
                "douyin_video_id": None,
            }
            get_video_storyboard.return_value = {
                "video_id": "ep_10",
                "available": True,
                "interval_seconds": 2,
                "frame_width": 160,
                "frame_height": 90,
                "columns": 5,
                "rows": 5,
                "sheets": [{"url": "/storyboards/ep_10/sheet_001.jpg"}],
            }
            response = self.client.get("/api/videos/ep_10/storyboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_id"], "ep_10")
        self.assertEqual(response.json()["available"], True)
        self.assertEqual(response.json()["sheets"][0]["url"], "/storyboards/ep_10/sheet_001.jpg")

    def test_get_video_storyboard_returns_unavailable_when_missing_asset(self) -> None:
        with (
            patch("services.api.routers.videos.get_video") as get_video,
            patch("services.api.routers.videos.get_video_storyboard") as get_video_storyboard,
        ):
            get_video.return_value = {
                "video_id": "ep_10",
                "title": "Demo ep10",
                "stream_url": "/api/videos/ep_10/stream",
                "danmaku_url": "/api/videos/ep_10/danmaku",
            }
            get_video_storyboard.return_value = {
                "video_id": "ep_10",
                "available": False,
                "interval_seconds": None,
                "frame_width": None,
                "frame_height": None,
                "columns": None,
                "rows": None,
                "sheets": [],
            }
            response = self.client.get("/api/videos/ep_10/storyboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["available"], False)
        self.assertEqual(response.json()["sheets"], [])

    def test_get_video_storyboard_not_found(self) -> None:
        with patch("services.api.routers.videos.get_video", return_value=None):
            response = self.client.get("/api/videos/missing/storyboard")

        self.assertEqual(response.status_code, 404)

    def test_create_playback_event(self) -> None:
        with patch("services.api.routers.playback_events.create_playback_event", return_value="evt_123"):
            response = self.client.post(
                "/api/playback-events",
                json={
                    "event_type": "playback_rate_change",
                    "user_id": "u_demo_001",
                    "video_id": "ep_10",
                    "client_time": 12.3,
                    "timestamp": 1779370000,
                    "extra": {"from_rate": 1.0, "to_rate": 1.5, "device": "expo_go"},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"event_id": "evt_123", "accepted": True})

    def test_create_playback_event_rejects_interaction_event(self) -> None:
        response = self.client.post(
            "/api/playback-events",
            json={
                "event_type": "option_click",
                "user_id": "u_demo_001",
                "video_id": "ep_10",
                "client_time": 12.3,
                "timestamp": 1779370000,
                "extra": {},
            },
        )

        self.assertEqual(response.status_code, 422)


class LocalModeApiRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        tmp_path = Path(self.tmpdir.name)
        (tmp_path / "demo_video.mp4").write_bytes(b"0" * 2048)
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        init_local_dev()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_local_mode_lists_demo_video(self) -> None:
        response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"][0]["video_id"], "demo_ep01")
        self.assertEqual(response.json()["videos"][0]["series_name"], "DramePulse Demo")
        self.assertEqual(response.json()["videos"][0]["episode_label"], "ep01")
        self.assertEqual(response.json()["videos"][0]["stream_url"], "/api/videos/demo_ep01/stream")
        self.assertEqual(response.json()["videos"][0]["danmaku_url"], "/api/videos/demo_ep01/danmaku")
        self.assertEqual(response.json()["videos"][0]["source"], "local")

    def test_local_mode_series_list_excludes_unassigned_episode_videos(self) -> None:
        sqlite_path = Path(os.environ["SQLITE_PATH"])
        local_oss_root = Path(os.environ["LOCAL_OSS_ROOT"])
        (local_oss_root / "loose_ep02.mp4").write_bytes(b"1" * 2048)

        connection = sqlite3.connect(sqlite_path)
        try:
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
                    oss_bucket,
                    oss_object_key,
                    content_type,
                    size,
                    source,
                    status
                )
                VALUES (?, NULL, NULL, ?, 2, 'ep02', 120, 'local', 'loose_ep02.mp4', 'video/mp4', 2048, 'local', 'active')
                """,
                ("ep_02", "Episode 02"),
            )
            connection.commit()
        finally:
            connection.close()

        response = self.client.get("/api/series")
        self.assertEqual(response.status_code, 200)
        series_ids = {item["series_id"] for item in response.json()["series"]}
        self.assertIn("demo", series_ids)
        self.assertNotIn("ep_02", series_ids)

    def test_local_mode_streams_demo_video(self) -> None:
        response = self.client.get("/api/videos/demo_ep01/stream")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "video/mp4")
        self.assertGreater(len(response.content), 1024)

    def test_local_mode_streams_range(self) -> None:
        response = self.client.get("/api/videos/demo_ep01/stream", headers={"Range": "bytes=0-3"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(response.content), 4)
        self.assertEqual(response.headers["content-range"].split("/")[0], "bytes 0-3")

    def test_local_mode_storyboard_legacy_url_is_fetchable(self) -> None:
        local_oss_root = Path(os.environ["LOCAL_OSS_ROOT"])
        sheet_path = local_oss_root / "storyboards" / "demo_ep01" / "sheet_001.jpg"
        sheet_path.parent.mkdir(parents=True, exist_ok=True)
        sheet_path.write_bytes(b"storyboard-image")
        manifest = {
            "video_id": "demo_ep01",
            "interval_seconds": 2,
            "frame_width": 160,
            "frame_height": 90,
            "columns": 5,
            "rows": 5,
            "sheets": [{"url": "/storyboards/demo_ep01/sheet_001.jpg"}],
        }
        connection = sqlite3.connect(os.environ["SQLITE_PATH"])
        try:
            connection.execute(
                """
                INSERT INTO video_storyboards (
                    video_id,
                    interval_seconds,
                    frame_width,
                    frame_height,
                    columns_count,
                    rows_count,
                    manifest_object_key,
                    manifest_json,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                ("demo_ep01", 2, 160, 90, 5, 5, "storyboards/demo_ep01/storyboard_manifest.json", json.dumps(manifest)),
            )
            connection.commit()
        finally:
            connection.close()

        storyboard_response = self.client.get("/api/videos/demo_ep01/storyboard")

        self.assertEqual(storyboard_response.status_code, 200)
        sheet_url = storyboard_response.json()["sheets"][0]["url"]
        self.assertEqual(sheet_url, "/storyboards/demo_ep01/sheet_001.jpg")
        sheet_response = self.client.get(sheet_url)
        self.assertEqual(sheet_response.status_code, 200)
        self.assertEqual(sheet_response.content, b"storyboard-image")

    def test_local_mode_records_playback_event(self) -> None:
        response = self.client.post(
            "/api/playback-events",
            json={
                "event_type": "pause",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "client_time": 12.3,
                "timestamp": 1779370000,
                "extra": {"device": "expo_go"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])


if __name__ == "__main__":
    unittest.main()

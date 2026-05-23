from __future__ import annotations

import os
from pathlib import Path
import shutil
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
                    "title": "第10集",
                    "episode_no": 10,
                    "duration": None,
                    "stream_url": "/api/videos/ep_10/stream",
                    "source": "oss",
                }
            ]
            response = self.client.get("/api/videos")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"][0]["video_id"], "ep_10")
        self.assertEqual(response.json()["videos"][0]["stream_url"], "/api/videos/ep_10/stream")

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
        shutil.copyfile(Path("demo_video.mp4"), tmp_path / "demo_video.mp4")
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
        self.assertEqual(response.json()["videos"][0]["stream_url"], "/api/videos/demo_ep01/stream")
        self.assertEqual(response.json()["videos"][0]["source"], "local")

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

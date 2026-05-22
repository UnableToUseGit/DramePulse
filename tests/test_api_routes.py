from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.main import create_app


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


if __name__ == "__main__":
    unittest.main()

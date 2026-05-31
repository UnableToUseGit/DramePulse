from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.scripts.init_local_dev import init_local_dev


class AdminDashboardApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        tmp_path = Path(self.tmpdir.name)
        shutil.copyfile(Path("apps/player-demo/assets/video/ep01.mp4"), tmp_path / "demo_video.mp4")
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        init_local_dev()
        self._move_demo_video_under_dramas()
        self._insert_legacy_video()
        self._insert_deleted_drama_video()
        self.client = TestClient(create_app())
        self._login_admin()

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def _move_demo_video_under_dramas(self) -> None:
        connection = sqlite3.connect(os.environ["SQLITE_PATH"])
        try:
            connection.execute(
                "UPDATE videos SET oss_object_key = ? WHERE video_id = ?",
                ("dramas/demo/episodes/ep01/video.mp4", "demo_ep01"),
            )
            connection.commit()
        finally:
            connection.close()

    def _login_admin(self) -> None:
        response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "Dramepulse"},
        )
        self.assertEqual(response.status_code, 200)

    def _insert_legacy_video(self) -> None:
        connection = sqlite3.connect(os.environ["SQLITE_PATH"])
        try:
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    oss_bucket, oss_object_key, content_type, size, source, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy_ep01",
                    "legacy",
                    "Legacy",
                    "Legacy Episode 01",
                    1,
                    "ep01",
                    "local",
                    "raw/legacy/ep01/video.mp4",
                    "video/mp4",
                    123,
                    "oss",
                    "active",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _insert_deleted_drama_video(self) -> None:
        connection = sqlite3.connect(os.environ["SQLITE_PATH"])
        try:
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    oss_bucket, oss_object_key, content_type, size, source, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "deleted_ep01",
                    "deleted",
                    "Deleted",
                    "Deleted Episode 01",
                    1,
                    "ep01",
                    "local",
                    "dramas/deleted/episodes/ep01/video.mp4",
                    "video/mp4",
                    123,
                    "oss",
                    "deleted",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_dashboard_returns_empty_event_stats(self) -> None:
        response = self.client.get("/api/admin/dashboard")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["series_count"], 1)
        self.assertEqual(payload["summary"]["episode_count"], 1)
        self.assertEqual(payload["summary"]["video_count"], 1)
        self.assertEqual(payload["summary"]["video_ready_count"], 1)
        self.assertEqual(payload["summary"]["danmaku_episode_count"], 0)
        self.assertGreater(payload["summary"]["danmaku_count"], 0)
        self.assertEqual(payload["summary"]["interaction_count"], 1)
        self.assertEqual(payload["summary"]["event_count"], 0)
        self.assertEqual(payload["summary"]["vote_count"], 0)
        self.assertEqual(payload["summary"]["click_rate"], 0)
        self.assertEqual(payload["summary"]["dismiss_rate"], 0)
        self.assertEqual(payload["series"][0]["series_id"], "demo")
        self.assertNotIn("legacy", {item["series_id"] for item in payload["series"]})
        deleted_series = next(item for item in payload["series"] if item["series_id"] == "deleted")
        self.assertEqual(deleted_series["status"], "deleted")
        self.assertEqual(deleted_series["asset_status"], "deleted")
        self.assertEqual(payload["series"][0]["episode_count"], 1)
        self.assertEqual(payload["series"][0]["video_ready_count"], 1)
        self.assertEqual(payload["series"][0]["danmaku_episode_count"], 0)
        self.assertEqual(payload["series"][0]["asset_status"], "missing_danmaku")
        demo_video = next(item for item in payload["videos"] if item["video_id"] == "demo_ep01")
        deleted_video = next(item for item in payload["videos"] if item["video_id"] == "deleted_ep01")
        self.assertEqual(demo_video["event_count"], 0)
        self.assertEqual(demo_video["vote_count"], 0)
        self.assertEqual(demo_video["asset_status"], "missing_danmaku")
        self.assertEqual(deleted_video["status"], "deleted")
        self.assertEqual(deleted_video["asset_status"], "deleted")
        self.assertEqual(payload["interactions"][0]["interaction_id"], "i_demo_ep01_001")
        self.assertEqual(payload["interactions"][0]["exposure_count"], 0)
        self.assertEqual(payload["interactions"][0]["click_count"], 0)
        self.assertEqual(payload["interactions"][0]["dismiss_count"], 0)
        self.assertEqual(payload["interactions"][0]["vote_count"], 0)
        self.assertEqual(len(payload["interactions"][0]["options"]), 3)
        self.assertEqual(payload["recent_events"], [])

    def test_dashboard_aggregates_events_and_votes(self) -> None:
        events = [
            {
                "event_type": "interaction_exposure",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "highlight_id": "h_demo_ep01_001",
                "interaction_id": "i_demo_ep01_001",
                "client_time": 9.0,
                "timestamp": 1779370000,
                "extra": {},
            },
            {
                "event_type": "option_click",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "highlight_id": "h_demo_ep01_001",
                "interaction_id": "i_demo_ep01_001",
                "option_id": "o_demo_ep01_001",
                "client_time": 10.0,
                "timestamp": 1779370001,
                "extra": {"interaction_type": "danmaku_poll"},
            },
            {
                "event_type": "interaction_dismiss",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "highlight_id": "h_demo_ep01_001",
                "interaction_id": "i_demo_ep01_001",
                "client_time": 12.0,
                "timestamp": 1779370002,
                "extra": {},
            },
        ]
        for event in events:
            response = self.client.post("/api/events", json=event)
            self.assertEqual(response.status_code, 200)

        response = self.client.get("/api/admin/dashboard")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["event_count"], 3)
        self.assertEqual(payload["summary"]["vote_count"], 1)
        self.assertEqual(payload["summary"]["click_rate"], 1.0)
        self.assertEqual(payload["summary"]["dismiss_rate"], 1.0)
        self.assertEqual(payload["series"][0]["event_count"], 3)
        self.assertEqual(payload["series"][0]["vote_count"], 1)
        demo_video = next(item for item in payload["videos"] if item["video_id"] == "demo_ep01")
        self.assertEqual(demo_video["event_count"], 3)
        self.assertEqual(demo_video["vote_count"], 1)
        interaction = payload["interactions"][0]
        self.assertEqual(interaction["exposure_count"], 1)
        self.assertEqual(interaction["click_count"], 1)
        self.assertEqual(interaction["dismiss_count"], 1)
        self.assertEqual(interaction["vote_count"], 1)
        self.assertEqual(interaction["options"][0]["vote_count"], 1)
        self.assertEqual(interaction["options"][0]["ratio"], 1.0)
        self.assertEqual(interaction["options"][1]["ratio"], 0)
        self.assertEqual(len(payload["recent_events"]), 3)
        self.assertEqual(payload["recent_events"][0]["event_type"], "interaction_dismiss")


if __name__ == "__main__":
    unittest.main()

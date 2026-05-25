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


class InteractionApiTest(unittest.TestCase):
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
        self.sqlite_path = tmp_path / "dramepulse.sqlite"
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_local_init_creates_mvp_tables(self) -> None:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()

        self.assertIn("danmaku_items", tables)
        self.assertIn("interaction_plans", tables)
        self.assertIn("interaction_options", tables)
        self.assertIn("user_events", tables)
        self.assertIn("interaction_option_stats", tables)

    def test_get_danmaku_returns_sorted_items(self) -> None:
        response = self.client.get("/api/videos/demo_ep01/danmaku?from_time=0&to_time=3")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["video_id"], "demo_ep01")
        self.assertGreater(len(payload["danmaku"]), 0)
        times = [item["client_time"] for item in payload["danmaku"]]
        self.assertEqual(times, sorted(times))

    def test_post_danmaku_writes_user_item(self) -> None:
        response = self.client.post(
            "/api/videos/demo_ep01/danmaku",
            json={
                "user_id": "u_demo_001",
                "client_time": 38.6,
                "text": "这也太反转了",
                "extra": {"device": "expo_go"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])

        list_response = self.client.get("/api/videos/demo_ep01/danmaku?from_time=38&to_time=39")
        texts = [item["text"] for item in list_response.json()["danmaku"]]
        self.assertIn("这也太反转了", texts)

    def test_get_interaction_plans_returns_active_danmaku_poll(self) -> None:
        response = self.client.get("/api/videos/demo_ep01/interaction-plans")

        self.assertEqual(response.status_code, 200)
        plans = response.json()["interaction_plans"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["interaction_type"], "danmaku_poll")
        self.assertEqual(plans[0]["status"], "active")
        self.assertEqual(plans[0]["result_time"], 18.0)
        self.assertEqual(len(plans[0]["options"]), 3)

    def test_option_click_updates_results(self) -> None:
        response = self.client.post(
            "/api/events",
            json={
                "event_type": "option_click",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "highlight_id": "h_demo_ep01_001",
                "interaction_id": "i_demo_ep01_001",
                "option_id": "o_demo_ep01_001",
                "client_time": 10.0,
                "timestamp": 1779370000,
                "extra": {"interaction_type": "danmaku_poll"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])

        results = self.client.get("/api/interactions/i_demo_ep01_001/results")
        self.assertEqual(results.status_code, 200)
        payload = results.json()
        self.assertEqual(payload["total_votes"], 1)
        self.assertEqual(payload["options"][0]["vote_count"], 1)
        self.assertEqual(payload["options"][0]["ratio"], 1.0)

    def test_late_option_click_returns_conflict(self) -> None:
        response = self.client.post(
            "/api/events",
            json={
                "event_type": "option_click",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "highlight_id": "h_demo_ep01_001",
                "interaction_id": "i_demo_ep01_001",
                "option_id": "o_demo_ep01_001",
                "client_time": 20.0,
                "timestamp": 1779370000,
                "extra": {},
            },
        )

        self.assertEqual(response.status_code, 409)

    def test_exposure_event_is_accepted_without_vote(self) -> None:
        response = self.client.post(
            "/api/events",
            json={
                "event_type": "interaction_exposure",
                "user_id": "u_demo_001",
                "video_id": "demo_ep01",
                "highlight_id": "h_demo_ep01_001",
                "interaction_id": "i_demo_ep01_001",
                "client_time": 9.0,
                "timestamp": 1779370000,
                "extra": {},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])

    def test_results_without_votes_returns_zero_ratios(self) -> None:
        response = self.client.get("/api/interactions/i_demo_ep01_001/results")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_votes"], 0)
        self.assertTrue(all(option["ratio"] == 0 for option in payload["options"]))


if __name__ == "__main__":
    unittest.main()

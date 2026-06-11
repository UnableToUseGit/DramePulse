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

    def test_upload_interaction_plans_requires_admin_login(self) -> None:
        response = self.client.post(
            "/api/admin/videos/demo_ep01/interaction-plans",
            json=self._upload_payload(),
        )

        self.assertEqual(response.status_code, 401)

    def test_upload_interaction_plans_rejects_missing_video(self) -> None:
        self._login_admin()

        response = self.client.post(
            "/api/admin/videos/missing_video/interaction-plans",
            json=self._upload_payload(),
        )

        self.assertEqual(response.status_code, 404)

    def test_upload_interaction_plans_replaces_existing_and_is_readable(self) -> None:
        self._login_admin()

        response = self.client.post(
            "/api/admin/videos/demo_ep01/interaction-plans",
            json=self._upload_payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "video_id": "demo_ep01",
                "uploaded_count": 1,
                "option_count": 2,
                "disabled_existing_count": 1,
                "active_count": 1,
            },
        )

        list_response = self.client.get("/api/videos/demo_ep01/interaction-plans")
        plans = list_response.json()["interaction_plans"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["interaction_id"], "i_uploaded_ep01_001")
        self.assertEqual(plans[0]["video_id"], "demo_ep01")
        self.assertEqual(plans[0]["question"], "What should happen next?")
        self.assertEqual([option["rank"] for option in plans[0]["options"]], [1, 2])

    def test_upload_interaction_plans_forces_active_status(self) -> None:
        self._login_admin()
        payload = self._upload_payload()
        payload["interaction_plans"][0]["status"] = "disabled"
        payload["interaction_plans"][0]["options"][0]["status"] = "disabled"
        payload["interaction_plans"][0]["options"][1]["status"] = "disabled"

        response = self.client.post(
            "/api/admin/videos/demo_ep01/interaction-plans",
            json=payload,
        )

        self.assertEqual(response.status_code, 200)
        plans = self.client.get("/api/videos/demo_ep01/interaction-plans").json()["interaction_plans"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["status"], "active")
        self.assertEqual([option["status"] for option in plans[0]["options"]], ["active", "active"])

    def test_upload_interaction_plans_without_replace_keeps_existing(self) -> None:
        self._login_admin()

        response = self.client.post(
            "/api/admin/videos/demo_ep01/interaction-plans",
            json=self._upload_payload(replace_existing=False),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["disabled_existing_count"], 0)

        plans = self.client.get("/api/videos/demo_ep01/interaction-plans").json()["interaction_plans"]
        self.assertEqual({plan["interaction_id"] for plan in plans}, {"i_demo_ep01_001", "i_uploaded_ep01_001"})

    def test_upload_interaction_plans_rejects_non_danmaku_poll(self) -> None:
        self._login_admin()
        payload = self._upload_payload()
        payload["interaction_plans"][0]["interaction_type"] = "emotion_pulse"

        response = self.client.post("/api/admin/videos/demo_ep01/interaction-plans", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_upload_interaction_plans_rejects_empty_options(self) -> None:
        self._login_admin()
        payload = self._upload_payload()
        payload["interaction_plans"][0]["options"] = []

        response = self.client.post("/api/admin/videos/demo_ep01/interaction-plans", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_upload_interaction_plans_rejects_invalid_time(self) -> None:
        self._login_admin()
        payload = self._upload_payload()
        payload["interaction_plans"][0]["expire_time"] = 8.0

        response = self.client.post("/api/admin/videos/demo_ep01/interaction-plans", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_upload_interaction_plans_rejects_duplicate_option_rank(self) -> None:
        self._login_admin()
        payload = self._upload_payload()
        payload["interaction_plans"][0]["options"][0]["rank"] = 1
        payload["interaction_plans"][0]["options"][1]["rank"] = 1

        response = self.client.post("/api/admin/videos/demo_ep01/interaction-plans", json=payload)

        self.assertEqual(response.status_code, 422)

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

    def _login_admin(self) -> None:
        response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "Dramepulse"},
        )
        self.assertEqual(response.status_code, 200)

    def _upload_payload(self, *, replace_existing: bool = True) -> dict[str, object]:
        return {
            "replace_existing": replace_existing,
            "interaction_plans": [
                {
                    "interaction_id": "i_uploaded_ep01_001",
                    "highlight_id": "h_uploaded_ep01_001",
                    "video_id": "ignored_video_id",
                    "trigger_time": 10.0,
                    "expire_time": 18.0,
                    "result_time": 20.0,
                    "interaction_type": "danmaku_poll",
                    "question": "What should happen next?",
                    "options": [
                        {
                            "option_id": "o_uploaded_ep01_001",
                            "text": "Option A",
                            "danmaku_text": "I choose A",
                            "base_score": 0.7,
                        },
                        {
                            "option_id": "o_uploaded_ep01_002",
                            "text": "Option B",
                            "danmaku_text": "I choose B",
                            "base_score": 0.6,
                        },
                    ],
                    "feedback": {"type": "poll_result", "show_ratio": True},
                    "display_position": "subtitle_safe_area",
                    "status": "active",
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()

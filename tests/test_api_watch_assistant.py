from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.main import create_app


class WatchAssistantApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_openai_key = os.environ.get("OPENAI_API_KEY")
        os.environ.pop("OPENAI_API_KEY", None)
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        if self.previous_openai_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = self.previous_openai_key

    def post_act(self, message: str, **extra: object):
        payload = {
            "message": message,
            "series_id": "demo",
            "video_id": "demo_ep01",
            "current_episode": 1,
            "current_time": 20,
            "duration": 90,
        }
        payload.update(extra)
        return self.client.post("/api/watch-assistant/act", json=payload)

    def test_story_question_calls_rag_and_returns_answer(self) -> None:
        with patch("services.api.watch_assistant.service.story_qa_service.ask") as ask:
            ask.return_value = {
                "answer": "男主刚刚暴露了真实身份。",
                "sources": [{"score": 0.9, "text": "身份揭露", "metadata": {"episode": 1}}],
            }
            response = self.post_act("刚才发生了什么？")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["reply"], "男主刚刚暴露了真实身份。")
        self.assertEqual(body["actions"][0]["type"], "answer")
        self.assertEqual(body["tool_calls"][0]["tool"], "story_qa")
        self.assertEqual(body["sources"][0]["text"], "身份揭露")
        ask.assert_called_once_with("刚才发生了什么？", "demo", 1, 20.0)

    def test_seek_relative_clamps_target_time(self) -> None:
        response = self.post_act("快进 100 秒", current_time=20, duration=90)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["actions"][0]["type"], "seek")
        self.assertEqual(body["actions"][0]["target_time"], 90)
        self.assertEqual(body["actions"][0]["relative_seconds"], 100)

    def test_next_episode_returns_frontend_action(self) -> None:
        response = self.post_act("下一集")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["actions"][0]["type"], "next_episode")

    def test_rag_error_is_displayable(self) -> None:
        with patch("services.api.watch_assistant.service.story_qa_service.ask", side_effect=RuntimeError("rag unavailable")):
            response = self.post_act("他是谁？")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("rag unavailable", body["reply"])
        self.assertEqual(body["tool_calls"][0]["status"], "error")

    def test_highlight_seek_uses_interaction_plan(self) -> None:
        with patch("services.api.watch_assistant.service.list_interaction_plans") as plans:
            plans.return_value = [
                {"interaction_id": "i1", "trigger_time": 12},
                {"interaction_id": "i2", "trigger_time": 42},
            ]
            response = self.post_act("快进到高光", current_time=20, duration=90)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["actions"]), 1)
        self.assertEqual(body["actions"][0]["type"], "seek")
        self.assertEqual(body["actions"][0]["target_time"], 42)

    def test_highlight_seek_falls_back_to_video_interaction_items(self) -> None:
        with (
            patch("services.api.watch_assistant.service.list_interaction_plans") as plans,
            patch("services.api.watch_assistant.service.list_video_interaction_items") as items,
        ):
            plans.return_value = []
            items.return_value = [
                {"interaction_id": "ia1", "trigger_time": 12},
                {"interaction_id": "ia2", "trigger_time": 42},
            ]
            response = self.post_act("跳到下一个高光点", current_time=20, duration=90)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["actions"][0]["type"], "seek")
        self.assertEqual(body["actions"][0]["target_time"], 42)

    def test_llm_seek_without_arguments_keeps_highlight_target_from_message(self) -> None:
        with (
            patch("services.api.watch_assistant.service._parse_with_llm") as parse_with_llm,
            patch("services.api.watch_assistant.service.list_interaction_plans") as plans,
        ):
            parse_with_llm.return_value = {"tools": [{"name": "seek", "arguments": {}}], "reply": ""}
            plans.return_value = [
                {"interaction_id": "i1", "trigger_time": 12},
                {"interaction_id": "i2", "trigger_time": 42},
            ]
            response = self.post_act("快进到高光", current_time=20, duration=90)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["actions"][0]["type"], "seek")
        self.assertEqual(body["actions"][0]["target_time"], 42)

    def test_chinese_next_highlight_prefers_rule_over_llm_reply(self) -> None:
        with (
            patch("services.api.watch_assistant.service._parse_with_llm") as parse_with_llm,
            patch("services.api.watch_assistant.service.list_interaction_plans") as plans,
        ):
            parse_with_llm.return_value = {
                "tools": [{"name": "seek", "arguments": {}}],
                "reply": "请提供具体的高光点时间或描述",
            }
            plans.return_value = [
                {"interaction_id": "i1", "trigger_time": 12},
                {"interaction_id": "i2", "trigger_time": 42},
            ]
            response = self.post_act("跳到下一个高光点", current_time=20, duration=90)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["actions"][0]["type"], "seek")
        self.assertEqual(body["actions"][0]["target_time"], 42)
        self.assertNotIn("请提供具体的高光点时间或描述", body["reply"])
        parse_with_llm.assert_not_called()

    def test_transcribe_accepts_audio_upload_with_mock_backend(self) -> None:
        response = self.client.post(
            "/api/watch-assistant/transcribe",
            data={
                "series_id": "demo",
                "video_id": "demo_ep01",
                "current_episode": "1",
                "current_time": "20",
                "duration": "1.25",
            },
            files={"audio": ("voice.m4a", b"fake-audio", "audio/mp4")},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["text"], "暂停")
        self.assertEqual(body["language"], "zh")
        self.assertEqual(body["duration_ms"], 1250)

    def test_transcribe_rejects_empty_audio(self) -> None:
        response = self.client.post(
            "/api/watch-assistant/transcribe",
            data={
                "series_id": "demo",
                "video_id": "demo_ep01",
                "current_episode": "1",
                "current_time": "20",
                "duration": "0",
            },
            files={"audio": ("voice.m4a", b"", "audio/mp4")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("没有录到声音", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

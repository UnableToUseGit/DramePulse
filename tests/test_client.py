from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from pipelines.client import VolcArkLlmClient


class _FakeResponse:
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"ok": True}),
                        }
                    }
                ]
            }
        ).encode("utf-8")


class VolcArkLlmClientTest(unittest.TestCase):
    def test_generate_json_multimodal_includes_video_url_blocks(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            captured["timeout"] = timeout
            captured["url"] = request.full_url  # type: ignore[attr-defined]
            captured["headers"] = dict(request.header_items())  # type: ignore[attr-defined]
            captured["payload"] = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
            return _FakeResponse()

        client = VolcArkLlmClient(
            api_key="test-key",
            model_name="doubao-test",
            timeout_sec=12,
        )
        with patch("pipelines.client.urllib_request.urlopen", fake_urlopen):
            result = client.generate_json_multimodal(
                system_prompt="system",
                user_prompt="user",
                video_urls=["https://example.com/video.mp4"],
                max_tokens=123,
            )

        payload = captured["payload"]
        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["url"], "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(payload["model"], "doubao-test")
        self.assertEqual(payload["max_tokens"], 123)
        self.assertEqual(payload["messages"][0]["content"], "system")
        self.assertEqual(
            payload["messages"][1]["content"],
            [
                {"type": "text", "text": "user"},
                {
                    "type": "video_url",
                    "video_url": {"url": "https://example.com/video.mp4"},
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()

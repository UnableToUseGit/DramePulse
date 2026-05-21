from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipelines.client import VolcArkLlmClient


class _FakeMessage:
    def __init__(self, content: object) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: object) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: object) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeCompletion:
        self.calls.append(kwargs)
        return _FakeCompletion('{"ok": true}')


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeArk:
    last_instance: "_FakeArk | None" = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.chat = _FakeChat()
        _FakeArk.last_instance = self


class VolcArkLlmClientTest(unittest.TestCase):
    def test_generate_json_multimodal_uses_ark_sdk_multi_image_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("pipelines.client.Ark", _FakeArk):
            image_path_1 = Path(tmpdir) / "frame_1.png"
            image_path_2 = Path(tmpdir) / "frame_2.jpg"
            image_path_1.write_bytes(b"png-bytes")
            image_path_2.write_bytes(b"jpg-bytes")
            client = VolcArkLlmClient(
                api_key="test-key",
                base_url="https://ark.example.com/api/v3",
                model_name="doubao-test",
                timeout_sec=12,
            )
            result = client.generate_json_multimodal(
                system_prompt="system",
                user_prompt="user",
                image_paths=[image_path_1, image_path_2],
                frame_timestamps_seconds=[0.0, 1.0],
                max_tokens=123,
            )

        self.assertEqual(result, {"ok": True})
        assert _FakeArk.last_instance is not None
        self.assertEqual(_FakeArk.last_instance.kwargs["api_key"], "test-key")
        self.assertEqual(_FakeArk.last_instance.kwargs["base_url"], "https://ark.example.com/api/v3")
        self.assertEqual(_FakeArk.last_instance.kwargs["timeout"], 12)
        payload = _FakeArk.last_instance.chat.completions.calls[0]
        self.assertEqual(payload["model"], "doubao-test")
        self.assertEqual(payload["max_tokens"], 123)
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        messages = payload["messages"]
        self.assertEqual(messages[0]["content"], "system")
        self.assertEqual(
            messages[1]["content"],
            [
                {"type": "text", "text": "user"},
                {"type": "text", "text": "[0.0 second]"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,cG5nLWJ5dGVz"},
                },
                {"type": "text", "text": "[1.0 second]"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,anBnLWJ5dGVz"},
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()

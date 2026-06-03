from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipelines.client import LlmResponseError, OpenAiLlmClient, VolcArkLlmClient


class _FakeMessage:
    def __init__(self, content: object) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: object) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: object) -> None:
        self.choices = [_FakeChoice(content)]
        self.id = "chatcmpl_test"
        self.usage = {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        }


class _FakeCompletions:
    def __init__(self, content: object = '{"ok": true}') -> None:
        self.calls: list[dict[str, object]] = []
        self.content = content

    def create(self, **kwargs: object) -> _FakeCompletion:
        self.calls.append(kwargs)
        return _FakeCompletion(self.content)


class _FakeChat:
    def __init__(self, content: object = '{"ok": true}') -> None:
        self.completions = _FakeCompletions(content)


class _FakeArk:
    last_instance: "_FakeArk | None" = None
    response_content: object = '{"ok": true}'

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.chat = _FakeChat(self.response_content)
        _FakeArk.last_instance = self


class VolcArkLlmClientTest(unittest.TestCase):
    def setUp(self) -> None:
        _FakeArk.response_content = '{"ok": true}'

    def test_generate_json_multimodal_uses_ark_sdk_multi_image_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("pipelines.client.volc_ark.Ark", _FakeArk):
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
        diagnostics = client.last_call_diagnostics
        self.assertEqual(diagnostics["status"], "success")
        self.assertEqual(diagnostics["model"], "doubao-test")
        self.assertEqual(diagnostics["max_tokens"], 123)
        self.assertEqual(diagnostics["image_count"], 2)
        self.assertEqual(diagnostics["frame_timestamps_count"], 2)
        self.assertEqual(diagnostics["request_id"], "chatcmpl_test")
        self.assertEqual(diagnostics["usage"]["prompt_tokens"], 11)
        self.assertEqual(diagnostics["usage"]["completion_tokens"], 7)
        self.assertEqual(diagnostics["usage"]["total_tokens"], 18)
        self.assertGreaterEqual(diagnostics["elapsed_sec"], 0.0)

    def test_generate_json_multimodal_preserves_raw_response_when_json_parse_fails(self) -> None:
        _FakeArk.response_content = "不是 JSON"

        with patch("pipelines.client.volc_ark.Ark", _FakeArk):
            client = VolcArkLlmClient(
                api_key="test-key",
                base_url="https://ark.example.com/api/v3",
                model_name="doubao-test",
                timeout_sec=12,
            )

            with self.assertRaises(LlmResponseError) as raised:
                client.generate_json_multimodal(
                    system_prompt="system",
                    user_prompt="user",
                    image_paths=[],
                    frame_timestamps_seconds=[],
                    max_tokens=123,
                )

        self.assertEqual(str(raised.exception), "LLM response is not valid JSON")
        self.assertEqual(raised.exception.raw_response_text, "不是 JSON")
        diagnostics = client.last_call_diagnostics
        self.assertEqual(diagnostics["status"], "failed")
        self.assertEqual(diagnostics["error_type"], "LlmResponseError")
        self.assertEqual(diagnostics["error"], "LLM response is not valid JSON")
        self.assertEqual(diagnostics["raw_response_text"], "不是 JSON")
        self.assertEqual(diagnostics["usage"]["total_tokens"], 18)

    def test_generate_json_multimodal_preserves_unexpected_raw_ark_response_shape(self) -> None:
        class FakeRawCompletions:
            def create(self, **kwargs: object) -> str:
                return "raw ark response"

        class FakeRawChat:
            completions = FakeRawCompletions()

        class FakeRawArk:
            def __init__(self, **kwargs: object) -> None:
                self.chat = FakeRawChat()

        with patch("pipelines.client.volc_ark.Ark", FakeRawArk):
            client = VolcArkLlmClient(
                api_key="test-key",
                base_url="https://ark.example.com/api/v3",
                model_name="doubao-test",
                timeout_sec=12,
            )

            with self.assertRaises(LlmResponseError) as raised:
                client.generate_json_multimodal(
                    system_prompt="system",
                    user_prompt="user",
                    image_paths=[],
                    frame_timestamps_seconds=[],
                    max_tokens=123,
                )

        self.assertEqual(str(raised.exception), "LLM response has unexpected shape: str")
        self.assertEqual(raised.exception.raw_response_text, "raw ark response")
        diagnostics = client.last_call_diagnostics
        self.assertEqual(diagnostics["status"], "failed")
        self.assertEqual(diagnostics["error_type"], "LlmResponseError")
        self.assertEqual(diagnostics["response_type"], "str")
        self.assertEqual(diagnostics["raw_response_text"], "raw ark response")

    def test_constructor_prefers_generic_env_values(self) -> None:
        with patch("pipelines.client.volc_ark.Ark", _FakeArk), patch.dict(
            "os.environ",
            {
                "API_KEY": "generic-key",
                "BASE_URL": "https://generic.example/api/v3",
                "MODEL": "generic-model",
                "ARK_API_KEY": "ark-key",
                "ARK_BASE_URL": "https://ark.example/api/v3",
                "ARK_MODEL": "ark-model",
            },
            clear=False,
        ):
            client = VolcArkLlmClient()

        self.assertEqual(client.api_key, "generic-key")
        self.assertEqual(client.base_url, "https://generic.example/api/v3")
        self.assertEqual(client.model_name, "generic-model")


class _FakeOpenAI:
    last_instance: "_FakeOpenAI | None" = None
    response_content: object = '{"ok": true}'

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.chat = _FakeChat(self.response_content)
        _FakeOpenAI.last_instance = self


class OpenAiLlmClientTest(unittest.TestCase):
    def setUp(self) -> None:
        _FakeOpenAI.response_content = '{"ok": true}'
        _FakeOpenAI.last_instance = None

    def test_generate_json_multimodal_uses_openai_chat_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI):
            image_path = Path(tmpdir) / "frame.png"
            image_path.write_bytes(b"png-bytes")
            client = OpenAiLlmClient(
                api_key="test-key",
                base_url="https://api.openai.example/v1",
                model_name="gpt-test",
                timeout_sec=22,
            )

            result = client.generate_json_multimodal(
                system_prompt="system",
                user_prompt="user",
                image_paths=[image_path],
                frame_timestamps_seconds=[3.0],
                max_tokens=456,
            )

        self.assertEqual(result, {"ok": True})
        assert _FakeOpenAI.last_instance is not None
        self.assertEqual(_FakeOpenAI.last_instance.kwargs["api_key"], "test-key")
        self.assertEqual(_FakeOpenAI.last_instance.kwargs["base_url"], "https://api.openai.example/v1")
        self.assertEqual(_FakeOpenAI.last_instance.kwargs["timeout"], 22)
        payload = _FakeOpenAI.last_instance.chat.completions.calls[0]
        self.assertEqual(payload["model"], "gpt-test")
        self.assertEqual(payload["max_tokens"], 456)
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertNotIn("extra_body", payload)
        self.assertEqual(payload["messages"][0]["content"], "system")
        self.assertEqual(
            payload["messages"][1]["content"],
            [
                {"type": "text", "text": "user"},
                {"type": "text", "text": "[3.0 second]"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,cG5nLWJ5dGVz"},
                },
            ],
        )
        self.assertEqual(client.last_call_diagnostics["status"], "success")
        self.assertEqual(client.last_call_diagnostics["provider"], "openai")
        self.assertEqual(client.last_call_diagnostics["usage"]["total_tokens"], 18)

    def test_generate_json_multimodal_disables_gpt_5_1_reasoning(self) -> None:
        with patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI):
            client = OpenAiLlmClient(api_key="test-key", model_name="gpt-5.1")

            client.generate_json_multimodal(
                system_prompt="system",
                user_prompt="user",
                image_paths=[],
                frame_timestamps_seconds=[],
            )

        assert _FakeOpenAI.last_instance is not None
        payload = _FakeOpenAI.last_instance.chat.completions.calls[0]
        self.assertEqual(payload["reasoning_effort"], "none")

    def test_generate_json_multimodal_disables_reasoning_for_configured_openai_model(self) -> None:
        with patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI):
            client = OpenAiLlmClient(api_key="test-key", model_name="gpt-5")

            client.generate_json_multimodal(
                system_prompt="system",
                user_prompt="user",
                image_paths=[],
                frame_timestamps_seconds=[],
            )

        assert _FakeOpenAI.last_instance is not None
        payload = _FakeOpenAI.last_instance.chat.completions.calls[0]
        self.assertEqual(payload["reasoning_effort"], "none")

    def test_generate_json_multimodal_always_requests_no_reasoning(self) -> None:
        with patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI):
            client = OpenAiLlmClient(api_key="test-key", model_name="gpt-4.1")

            client.generate_json_multimodal(
                system_prompt="system",
                user_prompt="user",
                image_paths=[],
                frame_timestamps_seconds=[],
            )

        assert _FakeOpenAI.last_instance is not None
        payload = _FakeOpenAI.last_instance.chat.completions.calls[0]
        self.assertEqual(payload["reasoning_effort"], "none")

    def test_generate_json_multimodal_preserves_raw_openai_response_when_json_parse_fails(self) -> None:
        _FakeOpenAI.response_content = "不是 JSON"

        with patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI):
            client = OpenAiLlmClient(api_key="test-key", model_name="gpt-test")

            with self.assertRaises(LlmResponseError) as raised:
                client.generate_json_multimodal(
                    system_prompt="system",
                    user_prompt="user",
                    image_paths=[],
                    frame_timestamps_seconds=[],
                )

        self.assertEqual(str(raised.exception), "LLM response is not valid JSON")
        self.assertEqual(raised.exception.raw_response_text, "不是 JSON")
        self.assertEqual(client.last_call_diagnostics["status"], "failed")
        self.assertEqual(client.last_call_diagnostics["provider"], "openai")
        self.assertEqual(client.last_call_diagnostics["raw_response_text"], "不是 JSON")

    def test_constructor_prefers_generic_env_values(self) -> None:
        with patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI), patch.dict(
            "os.environ",
            {
                "API_KEY": "generic-key",
                "BASE_URL": "https://generic.example/v1",
                "MODEL": "generic-model",
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_BASE_URL": "https://openai.example/v1",
                "OPENAI_MODEL": "openai-model",
            },
            clear=False,
        ):
            client = OpenAiLlmClient()

        self.assertEqual(client.api_key, "generic-key")
        self.assertEqual(client.base_url, "https://generic.example/v1")
        self.assertEqual(client.model_name, "generic-model")

    def test_constructor_defaults_to_gpt_5_5(self) -> None:
        with patch("pipelines.client.openai_client.OpenAI", _FakeOpenAI), patch.dict(
            "os.environ",
            {"API_KEY": "generic-key"},
            clear=True,
        ):
            client = OpenAiLlmClient()

        self.assertEqual(client.model_name, "gpt-5.5")


if __name__ == "__main__":
    unittest.main()

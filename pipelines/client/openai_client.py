from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from pipelines.client.common import build_multimodal_user_content, run_json_chat_completion


def reasoning_effort_for_model(model_name: str) -> str | None:
    normalized = model_name.strip().lower()
    return "none" # NOTE: 不打算使用低于 5.1 的模型
    # if normalized.startswith("gpt-5.1"):
    #     return "none"
    # if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
    #     return "minimal"
    # return None


class OpenAiLlmClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_sec: int = 90,
    ) -> None:
        self.api_key = api_key or os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None
        self.model_name = model_name or os.environ.get("MODEL") or os.environ.get("OPENAI_MODEL", "gpt-5.5")
        self.timeout_sec = timeout_sec
        self.last_call_diagnostics: dict[str, Any] = {}
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout_sec,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)

    def _set_last_call_diagnostics(self, diagnostics: dict[str, Any]) -> None:
        self.last_call_diagnostics = diagnostics

    def _build_user_content(
        self,
        *,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        return build_multimodal_user_content(
            user_prompt=user_prompt,
            image_paths=image_paths,
            frame_timestamps_seconds=frame_timestamps_seconds,
        )

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 1800,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": self._build_user_content(
                    user_prompt=user_prompt,
                    image_paths=image_paths,
                    frame_timestamps_seconds=frame_timestamps_seconds,
                ),
            },
        ]
        request_options: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        reasoning_effort = reasoning_effort_for_model(self.model_name)
        if reasoning_effort:
            request_options["reasoning_effort"] = reasoning_effort

        return run_json_chat_completion(
            provider="openai",
            model_name=self.model_name,
            max_tokens=max_tokens,
            image_count=len(image_paths or []),
            frame_timestamps_count=len(frame_timestamps_seconds or []),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            create_completion=lambda: self._client.chat.completions.create(**request_options),
            last_call_setter=self._set_last_call_diagnostics,
        )

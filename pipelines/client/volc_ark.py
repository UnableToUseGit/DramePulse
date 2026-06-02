from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from volcenginesdkarkruntime import Ark

from pipelines.client.common import build_multimodal_user_content, run_json_chat_completion


class VolcArkLlmClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_sec: int = 90,
    ) -> None:
        self.api_key = api_key or os.environ.get("API_KEY") or os.environ.get("ARK_API_KEY", "")
        self.base_url = (
            base_url
            or os.environ.get("BASE_URL")
            or os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        )
        self.model_name = model_name or os.environ.get("MODEL") or os.environ.get("ARK_MODEL", "doubao-seed-2-0-lite-260215")
        self.timeout_sec = timeout_sec
        self.last_call_diagnostics: dict[str, Any] = {}
        self._client = Ark(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_sec,
        )

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

        return run_json_chat_completion(
            provider="volc_ark",
            model_name=self.model_name,
            max_tokens=max_tokens,
            image_count=len(image_paths or []),
            frame_timestamps_count=len(frame_timestamps_seconds or []),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            create_completion=lambda: self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
                extra_body={"thinking": {"type": "disabled"}},
                response_format={"type": "json_object"},
            ),
            last_call_setter=self._set_last_call_diagnostics,
        )

from __future__ import annotations

import base64
import json
from json import JSONDecodeError
import os
from pathlib import Path
from typing import Any
from typing import Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request


class LlmClientProtocol(Protocol):
    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path],
        max_tokens: int = 1800,
    ) -> dict[str, Any]:
        ...


class OpenAICompatibleLlmClient:
    def __init__(
        self,
        *,
        api_base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_sec: int = 90,
    ) -> None:
        self.api_base_url = (api_base_url or os.environ.get("LLM_API_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model_name = model_name or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.timeout_sec = timeout_sec

    def _url(self) -> str:
        if self.api_base_url.endswith("/chat/completions"):
            return self.api_base_url
        return f"{self.api_base_url}/chat/completions"

    def _image_content_item(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        suffix = path.suffix.lower()
        mime = "image/jpeg"
        if suffix == ".png":
            mime = "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"},
        }

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path],
        max_tokens: int = 1800,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for path in image_paths:
            item = self._image_content_item(path)
            if item is not None:
                content.append(item)
        payload = {
            "model": self.model_name,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
        }
        request = urllib_request.Request(
            self._url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=self.timeout_sec) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib_error.URLError as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to call LLM endpoint: {exc}") from exc
        content_value = response_payload["choices"][0]["message"]["content"]
        if isinstance(content_value, list):
            parts: list[str] = []
            for item in content_value:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            content_value = "\n".join(parts)
        if not isinstance(content_value, str):
            content_value = str(content_value)
        try:
            return json.loads(content_value)
        except JSONDecodeError as exc:
            raise RuntimeError("LLM response is not valid JSON") from exc

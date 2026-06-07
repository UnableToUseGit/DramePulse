from __future__ import annotations

import base64
import json
from json import JSONDecodeError
import os
from pathlib import Path
from typing import Any, Protocol

try:  # pragma: no cover - exercised through the real SDK in integration environments.
    from volcenginesdkarkruntime import Ark
except ImportError:  # pragma: no cover - unit tests patch Ark with a fake client.
    Ark = None  # type: ignore[assignment]


class LlmClientProtocol(Protocol):
    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 4800,
    ) -> dict[str, Any]:
        ...


def _clean_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _image_path_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_type = "image/jpeg"
    if suffix == ".png":
        mime_type = "image/png"
    elif suffix == ".webp":
        mime_type = "image/webp"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _response_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if "text" in item:
                parts.append(_clean_text(item["text"]))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return str(content)


def _parse_json_content(content: Any) -> dict[str, Any]:
    text = _response_content_to_text(content).strip()
    if not text:
        raise RuntimeError("LLM response is empty")
    try:
        parsed = json.loads(text)
    except JSONDecodeError as exc:
        raise RuntimeError("LLM response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM response JSON must be an object")
    return parsed


class VolcArkLlmClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_sec: int = 90,
    ) -> None:
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        self.base_url = base_url or os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.model_name = model_name or os.environ.get("ARK_MODEL", "doubao-seed-2-0-lite-260215")
        self.timeout_sec = timeout_sec
        if Ark is None:
            raise RuntimeError("volcenginesdkarkruntime is required to use VolcArkLlmClient")
        self._client = Ark(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_sec,
        )

    def _build_user_content(
        self,
        *,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        image_paths = image_paths or []
        frame_timestamps_seconds = frame_timestamps_seconds or []
        for index, image_path in enumerate(image_paths):
            if index < len(frame_timestamps_seconds):
                content.append(
                    {
                        "type": "text",
                        "text": f"[{frame_timestamps_seconds[index]:.1f} second]",
                    }
                )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _image_path_to_data_url(image_path)},
                }
            )
        return content

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

        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.2,
            extra_body={"thinking": {"type": "disabled"}},
            response_format={"type": "json_object"},
        )
        return _parse_json_content(response.choices[0].message.content)

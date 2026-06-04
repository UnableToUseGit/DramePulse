from __future__ import annotations

import base64
import json
from json import JSONDecodeError
from pathlib import Path
import time
from typing import Any, Callable, Protocol


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


class LlmResponseError(RuntimeError):
    def __init__(self, message: str, *, raw_response_text: str = "") -> None:
        super().__init__(message)
        self.raw_response_text = raw_response_text


def clean_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def image_path_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_type = "image/jpeg"
    if suffix == ".png":
        mime_type = "image/png"
    elif suffix == ".webp":
        mime_type = "image/webp"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def response_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if "text" in item:
                parts.append(clean_text(item["text"]))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return str(content)


def extract_json_object_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    try:
        parsed = json.loads(stripped)
    except JSONDecodeError:
        pass
    else:
        if isinstance(parsed, dict):
            return stripped

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, end_index = decoder.raw_decode(stripped[index:])
        except JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return stripped[index : index + end_index]
    return stripped


def parse_json_content(content: Any) -> dict[str, Any]:
    text = response_content_to_text(content).strip()
    if not text:
        raise LlmResponseError("LLM response is empty", raw_response_text=text)
    json_text = extract_json_object_text(text)
    try:
        parsed = json.loads(json_text)
    except JSONDecodeError as exc:
        import json_repair

        try:
            repaired = json_repair.loads(json_text)
        except Exception as repair_exc:
            raise LlmResponseError("LLM response is not valid JSON", raw_response_text=text) from repair_exc
        if not isinstance(repaired, dict):
            raise LlmResponseError("LLM response is not valid JSON", raw_response_text=text) from exc
        return repaired
    if not isinstance(parsed, dict):
        raise LlmResponseError("LLM response JSON must be an object", raw_response_text=text)
    return parsed


def get_attr_or_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    result: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = value
    return result


def response_to_raw_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, bytes):
        return response.decode("utf-8", errors="replace")
    try:
        return json.dumps(response, ensure_ascii=False, default=str)
    except TypeError:
        return str(response)


def response_to_message_content(response: Any) -> Any:
    choices = get_attr_or_key(response, "choices")
    if not isinstance(choices, list) or not choices:
        raise LlmResponseError(
            f"LLM response has unexpected shape: {type(response).__name__}",
            raw_response_text=response_to_raw_text(response),
        )
    first_choice = choices[0]
    message = get_attr_or_key(first_choice, "message")
    content = get_attr_or_key(message, "content")
    if content is None:
        raise LlmResponseError(
            "LLM response message content is empty or missing",
            raw_response_text=response_to_raw_text(response),
        )
    return content


def build_multimodal_user_content(
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
                "image_url": {"url": image_path_to_data_url(image_path)},
            }
        )
    return content


def run_json_chat_completion(
    *,
    provider: str,
    model_name: str,
    max_tokens: int,
    image_count: int,
    frame_timestamps_count: int,
    system_prompt: str,
    user_prompt: str,
    create_completion: Callable[[], Any],
    last_call_setter: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    base_diagnostics: dict[str, Any] = {
        "provider": provider,
        "model": model_name,
        "max_tokens": max_tokens,
        "image_count": image_count,
        "frame_timestamps_count": frame_timestamps_count,
        "system_prompt_char_count": len(system_prompt),
        "user_prompt_char_count": len(user_prompt),
    }
    response: Any = None

    try:
        response = create_completion()
        parsed = parse_json_content(response_to_message_content(response))
    except Exception as exc:
        diagnostics = dict(base_diagnostics)
        diagnostics.update(
            {
                "status": "failed",
                "elapsed_sec": round(time.perf_counter() - started_at, 3),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "response_type": type(response).__name__ if response is not None else None,
                "usage": usage_to_dict(get_attr_or_key(response, "usage")) if response is not None else {},
                "request_id": get_attr_or_key(response, "id") if response is not None else None,
            }
        )
        raw_response_text = getattr(exc, "raw_response_text", "")
        if isinstance(raw_response_text, str) and raw_response_text:
            diagnostics["raw_response_text"] = raw_response_text
        last_call_setter(diagnostics)
        raise

    last_call_setter(
        {
            **base_diagnostics,
            "status": "success",
            "elapsed_sec": round(time.perf_counter() - started_at, 3),
            "usage": usage_to_dict(get_attr_or_key(response, "usage")),
            "request_id": get_attr_or_key(response, "id"),
        }
    )
    return parsed

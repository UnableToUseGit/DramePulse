from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from volcenginesdkarkruntime import Ark

from pipelines.client.common import image_path_to_data_url


DEFAULT_SEEDANCE_MODEL = "doubao-seedance-2-0-260128"
DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


@dataclass(frozen=True)
class SeedanceTaskResult:
    task_id: str
    status: str
    video_url: str | None = None


def _asset_image_url(value: Any) -> str:
    path_text = str(value or "")
    if not path_text:
        raise ValueError("Seedance image reference cannot be empty")
    path = Path(path_text)
    if path.exists():
        return image_path_to_data_url(path)
    return path_text


def _audio_path_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_type = "audio/mpeg"
    if suffix == ".wav":
        mime_type = "audio/wav"
    encoded = path.read_bytes()
    import base64

    return f"data:{mime_type};base64,{base64.b64encode(encoded).decode('ascii')}"


def _asset_audio_url(value: Any) -> str:
    path_text = str(value or "")
    if not path_text:
        raise ValueError("Seedance audio reference cannot be empty")
    path = Path(path_text)
    if path.exists():
        if path.suffix.lower() not in {".mp3", ".wav"}:
            raise ValueError(f"Seedance audio reference must be mp3 or wav: {path_text}")
        return _audio_path_to_data_url(path)
    return path_text


class SeedanceClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        ark_client: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        self.base_url = base_url or os.environ.get("ARK_BASE_URL", DEFAULT_ARK_BASE_URL)
        self._client = ark_client or Ark(api_key=self.api_key, base_url=self.base_url)

    def create_task(
        self,
        *,
        model: str,
        content: list[dict[str, Any]],
        generate_audio: bool,
        ratio: str,
        duration: int,
        watermark: bool,
    ) -> SeedanceTaskResult:
        response = self._client.content_generation.tasks.create(
            model=model,
            content=content,
            generate_audio=generate_audio,
            ratio=ratio,
            duration=duration,
            watermark=watermark,
        )
        return _parse_seedance_task_response(response)

    def get_task(self, task_id: str) -> SeedanceTaskResult:
        response = self._client.content_generation.tasks.get(task_id=task_id)
        return _parse_seedance_task_response(response)


def _field(response: Any, name: str, default: Any = None) -> Any:
    if isinstance(response, dict):
        return response.get(name, default)
    return getattr(response, name, default)


def _parse_seedance_task_response(response: Any) -> SeedanceTaskResult:
    task_id = _field(response, "id") or _field(response, "task_id") or _field(response, "taskId")
    status = _field(response, "status", "unknown")
    video_url = _field(response, "video_url") or _field(response, "output_video_url")
    result = _field(response, "result")
    if not video_url and isinstance(result, dict):
        video_url = result.get("video_url") or result.get("output_video_url")
    content = _field(response, "content")
    if not video_url and isinstance(content, dict):
        video_url = content.get("video_url")
    if not video_url and content is not None:
        video_url = getattr(content, "video_url", None) or getattr(content, "file_url", None)
    if not task_id:
        raise RuntimeError("Seedance task response missing task id")
    return SeedanceTaskResult(task_id=str(task_id), status=str(status), video_url=video_url)


def attach_seedance_render(
    asset: dict[str, Any],
    task_result: SeedanceTaskResult,
) -> dict[str, Any]:
    updated = dict(asset)
    updated["render"] = {
        **dict(asset.get("render") or {}),
        "render_status": task_result.status,
        "provider": "volcengine_seedance",
        "provider_job_id": task_result.task_id,
        "output_video_url": task_result.video_url,
    }
    return updated

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from openai import OpenAI
import requests

from pipelines.client.common import image_path_to_data_url


DEFAULT_SEEDREAM_MODEL = "doubao-seedream-5-0-260128"
DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


@dataclass(frozen=True)
class SeedreamImageRequest:
    prompt: str
    reference_image_paths: list[Path]
    size: str = "2K"
    output_format: str = "png"
    response_format: str = "url"
    watermark: bool = False
    sequential_image_generation: str = "disabled"


@dataclass(frozen=True)
class SeedreamGenerationResult:
    url: str | None = None
    b64_json: str | None = None


class SeedreamImageGenerationClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        openai_client: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        self.base_url = base_url or os.environ.get("ARK_BASE_URL", DEFAULT_ARK_BASE_URL)
        self.model_name = model_name or os.environ.get("ARK_SEEDREAM_MODEL", DEFAULT_SEEDREAM_MODEL)
        self._client = openai_client or OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate_image(self, request: SeedreamImageRequest) -> SeedreamGenerationResult:
        if not request.prompt.strip():
            raise ValueError("Seedream image request requires `prompt`")
        image_inputs = [image_path_to_data_url(path) for path in request.reference_image_paths]
        response = self._client.images.generate(
            model=self.model_name,
            prompt=request.prompt,
            size=request.size,
            output_format=request.output_format,
            response_format=request.response_format,
            extra_body={
                "image": image_inputs,
                "watermark": request.watermark,
                "sequential_image_generation": request.sequential_image_generation,
            },
        )
        data = getattr(response, "data", None)
        if not data:
            raise RuntimeError("Seedream image generation returned no image data")
        first_image = data[0]
        return SeedreamGenerationResult(
            url=getattr(first_image, "url", None),
            b64_json=getattr(first_image, "b64_json", None),
        )


def download_generated_image(
    url: str,
    output_path: Path,
    *,
    http_client: Any = requests,
    timeout_sec: int = 60,
) -> Path:
    if not url.strip():
        raise ValueError("Generated image URL is required")
    response = http_client.get(url, timeout=timeout_sec)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path

from __future__ import annotations

from pathlib import Path
import subprocess
import time
from typing import Any, Callable

import requests

from pipelines.highlight_commerce.seedream_generation import (
    SeedreamImageGenerationClient,
    SeedreamImageRequest,
    download_generated_image,
)
from pipelines.highlight_commerce.seedance_generation import (
    DEFAULT_SEEDANCE_MODEL,
    SeedanceClient,
    SeedanceTaskResult,
    _asset_audio_url,
    _asset_image_url,
    attach_seedance_render,
)


CommandRunner = Callable[[list[str]], None]
DEFAULT_STYLE_REFERENCE_DIR = Path("data/role-commerce-v2/styles")


def _default_command_runner(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def _require_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Highlight commerce asset requires `{key}`")
    return value


def _request_plan(asset: dict[str, Any]) -> dict[str, Any]:
    return _require_dict(asset, "seedance_request_plan")


def validate_highlight_commerce_asset(asset: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(asset, dict):
        raise ValueError("Highlight commerce asset must be a JSON object")
    if not _clean_text(asset.get("campaign_id")):
        raise ValueError("Highlight commerce asset requires `campaign_id`")
    plan = _request_plan(asset)
    reference_images = plan.get("reference_images")
    if not isinstance(reference_images, list) or not reference_images:
        raise ValueError("seedance_request_plan requires non-empty `reference_images`")
    for item in reference_images:
        if not isinstance(item, dict):
            raise ValueError("reference_images must contain objects")
        path = Path(_clean_text(item.get("path")))
        if not path.exists():
            raise ValueError(f"Reference image does not exist: {path}")
    reference_audio = plan.get("reference_audio", [])
    if not isinstance(reference_audio, list):
        raise ValueError("seedance_request_plan.reference_audio must be a list")
    for item in reference_audio:
        if not isinstance(item, dict):
            raise ValueError("reference_audio must contain objects")
        path = Path(_clean_text(item.get("source_path")))
        if not path.exists():
            raise ValueError(f"Reference audio does not exist: {path}")
    return asset


def _style_reference_paths(style_reference_dir: Path) -> list[Path]:
    if not style_reference_dir.exists():
        raise ValueError(f"Style reference directory does not exist: {style_reference_dir}")
    paths = [
        path
        for path in sorted(style_reference_dir.iterdir())
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not paths:
        raise ValueError(f"Style reference directory contains no image files: {style_reference_dir}")
    return paths


def _source_assets(asset: dict[str, Any]) -> dict[str, Any]:
    return _require_dict(asset, "source_assets")


def _seedream_prompt_for(kind: str, asset: dict[str, Any]) -> str:
    highlight = asset.get("highlight") if isinstance(asset.get("highlight"), dict) else {}
    if kind == "highlight":
        return "\n".join(
            [
                "Create a privacy-safe 2D short-drama cartoon highlight reference image.",
                "Use the first reference image for composition and story moment: a close-distance romantic kiss ending.",
                "Use the remaining reference images only for the shared cartoon style.",
                f"Highlight hook: {highlight.get('hook_description', '')}",
                "Preserve the intimate distance, romantic tension, vertical short-drama composition, indoor mood, and character relationship.",
                "Do not create photorealistic human faces, celebrity likeness, real-person identity, or photographic texture.",
                "Do not make it childish chibi; keep mature drama-spinoff cartoon proportions.",
            ]
        )
    if kind == "male":
        return "\n".join(
            [
                "Create one privacy-safe 2D short-drama cartoon avatar for the male lead.",
                "Use the first reference image for character identity cues: age bracket, hairstyle silhouette, outfit symbols, temperament, posture.",
                "Use the remaining reference images only for the shared cartoon style.",
                "Do not create photorealistic human face, celebrity likeness, real-person identity, or photographic texture.",
                "Keep mature drama-spinoff cartoon proportions, not childish chibi.",
            ]
        )
    if kind == "female":
        return "\n".join(
            [
                "Create one privacy-safe 2D short-drama cartoon avatar for the female lead.",
                "Use the first reference image for character identity cues: age bracket, hairstyle silhouette, outfit symbols, temperament, posture.",
                "Use the remaining reference images only for the shared cartoon style.",
                "Do not create photorealistic human face, celebrity likeness, real-person identity, or photographic texture.",
                "Keep mature drama-spinoff cartoon proportions, not childish chibi.",
            ]
        )
    raise ValueError(f"Unsupported cartoon reference kind: {kind}")


def _generate_seedream_image(
    *,
    kind: str,
    source_image_path: Path,
    output_path: Path,
    asset: dict[str, Any],
    style_reference_paths: list[Path],
    seedream_client: Any,
    http_client: Any,
) -> Path:
    result = seedream_client.generate_image(
        SeedreamImageRequest(
            prompt=_seedream_prompt_for(kind, asset),
            reference_image_paths=[source_image_path, *style_reference_paths],
            size="2K",
            output_format="png",
            response_format="url",
            watermark=False,
        )
    )
    if not result.url:
        raise RuntimeError(f"Seedream did not return URL for {kind}")
    download_generated_image(result.url, output_path, http_client=http_client)
    return output_path


def generate_privacy_safe_cartoon_references(
    asset: dict[str, Any],
    *,
    output_dir: Path,
    style_reference_paths: list[Path] | None = None,
    style_reference_dir: Path = DEFAULT_STYLE_REFERENCE_DIR,
    seedream_client: Any | None = None,
    http_client: Any = requests,
) -> dict[str, Any]:
    validated_asset = validate_highlight_commerce_asset(asset)
    source_assets = _source_assets(validated_asset)
    styles = style_reference_paths or _style_reference_paths(style_reference_dir)
    for path in styles:
        if not path.exists():
            raise ValueError(f"Style reference image does not exist: {path}")
    client = seedream_client or SeedreamImageGenerationClient()
    output_dir.mkdir(parents=True, exist_ok=True)

    highlight_path = _generate_seedream_image(
        kind="highlight",
        source_image_path=Path(str(source_assets["highlight_image_path"])),
        output_path=output_dir / "cartoon_highlight_reference.png",
        asset=validated_asset,
        style_reference_paths=styles,
        seedream_client=client,
        http_client=http_client,
    )
    male_path = _generate_seedream_image(
        kind="male",
        source_image_path=Path(str(source_assets["male_character_image_path"])),
        output_path=output_dir / "cartoon_male_avatar.png",
        asset=validated_asset,
        style_reference_paths=styles,
        seedream_client=client,
        http_client=http_client,
    )
    female_path = _generate_seedream_image(
        kind="female",
        source_image_path=Path(str(source_assets["female_character_image_path"])),
        output_path=output_dir / "cartoon_female_avatar.png",
        asset=validated_asset,
        style_reference_paths=styles,
        seedream_client=client,
        http_client=http_client,
    )

    updated = dict(validated_asset)
    plan = dict(_request_plan(validated_asset))
    product = _require_dict(validated_asset, "product")
    plan["reference_images"] = [
        {
            "role": "cartoon_highlight_reference",
            "path": str(highlight_path),
            "instruction": "卡通高光参考图，承接亲吻收尾和亲密关系。",
        },
        {
            "role": "cartoon_male_avatar",
            "path": str(male_path),
            "instruction": "男主卡通角色形象参考。",
        },
        {
            "role": "cartoon_female_avatar",
            "path": str(female_path),
            "instruction": "女主卡通角色形象参考。",
        },
        {
            "role": "product",
            "path": str(product["image_path"]),
            "instruction": "商品外观和特写参考。",
        },
    ]
    notes = list(plan.get("prompt_notes", [])) if isinstance(plan.get("prompt_notes"), list) else []
    notes.append("Seedance 阶段只使用卡通高光图和卡通角色图，不直接传真人图。")
    plan["prompt_notes"] = notes
    updated["seedance_request_plan"] = plan
    updated["cartoon_references"] = {
        "style_reference_paths": [str(path) for path in styles],
        "highlight_reference_path": str(highlight_path),
        "male_avatar_path": str(male_path),
        "female_avatar_path": str(female_path),
    }
    return updated


class HighlightCommerceCartoonPipeline:
    def __init__(
        self,
        *,
        seedream_client: Any | None = None,
        style_reference_dir: Path = DEFAULT_STYLE_REFERENCE_DIR,
        http_client: Any = requests,
    ) -> None:
        self.seedream_client = seedream_client
        self.style_reference_dir = style_reference_dir
        self.http_client = http_client

    def run(self, asset: dict[str, Any], *, output_dir: Path) -> dict[str, Any]:
        return generate_privacy_safe_cartoon_references(
            asset,
            output_dir=output_dir,
            style_reference_dir=self.style_reference_dir,
            seedream_client=self.seedream_client,
            http_client=self.http_client,
        )


def build_highlight_commerce_prompt(asset: dict[str, Any]) -> str:
    highlight = _require_dict(asset, "highlight")
    product = _require_dict(asset, "product")
    plan = _request_plan(asset)
    storyboard_lines: list[str] = []
    for shot in asset.get("storyboard", []):
        if not isinstance(shot, dict):
            continue
        dialogue_lines = []
        for dialogue in shot.get("dialogue", []):
            if isinstance(dialogue, dict):
                dialogue_lines.append(f"{dialogue.get('speaker', '')}: \"{dialogue.get('text', '')}\"")
        storyboard_lines.append(
            "\n".join(
                [
                    f"- {shot.get('shot_id', '')} ({shot.get('start_sec', '')}-{shot.get('end_sec', '')}s): {shot.get('description', '')}",
                    f"  Visual: {shot.get('visual_prompt', '')}",
                    f"  Dialogue: {' / '.join(dialogue_lines) if dialogue_lines else 'none'}",
                    f"  Product visibility: {shot.get('product_visibility', '')}",
                ]
            )
        )
    notes = [str(note) for note in plan.get("prompt_notes", []) if str(note).strip()]
    image_roles = []
    for item in plan.get("reference_images", []):
        if isinstance(item, dict):
            image_roles.append(str(item.get("role", "")).strip())
    image_order = ", ".join(role for role in image_roles if role) or "highlight scene and product"
    return "\n".join(
        [
            "Generate a 9:16 vertical short-drama commerce video that starts from a drama highlight and naturally bridges into product recommendation.",
            "Keep the original short-drama look. Do not generate an e-commerce livestream background. 不要生成电商直播背景。",
            f"Duration: {plan.get('duration', asset.get('target_duration_sec', 12))} seconds.",
            f"Highlight hook: {highlight.get('hook_description', '')}",
            f"Continuity goal: {highlight.get('continuity_goal', '')}",
            f"Product: {product.get('product_name', '')} / {product.get('category', '')}",
            f"Selling points: {', '.join(product.get('selling_points', [])) if isinstance(product.get('selling_points'), list) else ''}",
            f"Avoid claims: {', '.join(product.get('must_avoid', [])) if isinstance(product.get('must_avoid'), list) else ''}",
            f"Use reference images in order: {image_order}.",
            "Use reference audio for character timbre. Keep speaker lines assigned to the correct character.",
            "Exact storyboard:",
            *storyboard_lines,
            "Additional constraints:",
            *[f"- {note}" for note in notes],
        ]
    )


def ensure_reference_audio_clips(
    asset: dict[str, Any],
    *,
    output_dir: Path,
    command_runner: CommandRunner = _default_command_runner,
) -> list[Path]:
    plan = _request_plan(asset)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    for item in plan.get("reference_audio", []):
        if not isinstance(item, dict):
            continue
        speaker = _clean_text(item.get("speaker")) or f"speaker_{len(output_paths) + 1}"
        source_path = Path(_clean_text(item.get("source_path")))
        start_sec = float(item.get("trim_start_sec", 0.0))
        end_sec = float(item.get("trim_end_sec", 0.0))
        if end_sec <= start_sec:
            raise ValueError(f"Invalid audio trim range for {speaker}")
        output_path = output_dir / f"{speaker}_reference_audio.mp3"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-to",
            f"{end_sec:.3f}",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "96k",
            str(output_path),
        ]
        command_runner(command)
        output_paths.append(output_path)
    return output_paths


def _build_seedance_content(asset: dict[str, Any], audio_paths: list[Path]) -> list[dict[str, Any]]:
    plan = _request_plan(asset)
    content: list[dict[str, Any]] = [{"type": "text", "text": build_highlight_commerce_prompt(asset)}]
    for item in plan.get("reference_images", []):
        if not isinstance(item, dict):
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _asset_image_url(item.get("path"))},
                "role": "reference_image",
            }
        )
    for path in audio_paths:
        content.append(
            {
                "type": "audio_url",
                "audio_url": {"url": _asset_audio_url(path)},
                "role": "reference_audio",
            }
        )
    return content


def _download_video(url: str, output_path: Path, http_client: Any = requests) -> Path:
    response = http_client.get(url, timeout=120)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path


class HighlightCommerceSeedancePipeline:
    def __init__(
        self,
        *,
        seedance_client: Any | None = None,
        wait_for_completion: bool = True,
        poll_interval_sec: float = 2.0,
        max_poll_attempts: int = 120,
        command_runner: CommandRunner = _default_command_runner,
        http_client: Any = requests,
        status_callback: Callable[[SeedanceTaskResult], None] | None = None,
    ) -> None:
        self.seedance_client = seedance_client or SeedanceClient()
        self.wait_for_completion = wait_for_completion
        self.poll_interval_sec = max(0.0, poll_interval_sec)
        self.max_poll_attempts = max(1, max_poll_attempts)
        self.command_runner = command_runner
        self.http_client = http_client
        self.status_callback = status_callback

    def _emit_status(self, task_result: SeedanceTaskResult) -> None:
        if self.status_callback is not None:
            self.status_callback(task_result)

    def _wait_for_task(self, task_id: str) -> SeedanceTaskResult:
        last_result = SeedanceTaskResult(task_id=task_id, status="queued")
        terminal_statuses = {"succeeded", "failed", "expired", "cancelled", "canceled"}
        for attempt in range(self.max_poll_attempts):
            last_result = self.seedance_client.get_task(task_id)
            self._emit_status(last_result)
            if last_result.status in terminal_statuses:
                return last_result
            if attempt < self.max_poll_attempts - 1 and self.poll_interval_sec > 0:
                time.sleep(self.poll_interval_sec)
        return last_result

    def run(self, asset: dict[str, Any], *, output_dir: Path) -> dict[str, Any]:
        validated_asset = validate_highlight_commerce_asset(asset)
        plan = _request_plan(validated_asset)
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_paths = ensure_reference_audio_clips(
            validated_asset,
            output_dir=output_dir,
            command_runner=self.command_runner,
        )
        task_result = self.seedance_client.create_task(
            model=str(plan.get("model") or DEFAULT_SEEDANCE_MODEL),
            content=_build_seedance_content(validated_asset, audio_paths),
            generate_audio=bool(plan.get("generate_audio", True)),
            ratio=str(plan.get("ratio") or "9:16"),
            duration=int(plan.get("duration") or validated_asset.get("target_duration_sec", 12)),
            watermark=bool(plan.get("watermark", False)),
        )
        self._emit_status(task_result)
        if self.wait_for_completion:
            task_result = self._wait_for_task(task_result.task_id)
        updated = attach_seedance_render(validated_asset, task_result)
        if task_result.video_url:
            video_path = output_dir / "highlight_commerce_seedance.mp4"
            _download_video(task_result.video_url, video_path, http_client=self.http_client)
            updated["render"]["output_video_path"] = str(video_path)
        return updated

    def update_existing_task(
        self,
        asset: dict[str, Any],
        *,
        task_id: str,
        output_dir: Path,
    ) -> dict[str, Any]:
        validated_asset = validate_highlight_commerce_asset(asset)
        clean_task_id = _clean_text(task_id)
        if not clean_task_id:
            raise ValueError("Seedance task id is required")
        output_dir.mkdir(parents=True, exist_ok=True)
        if self.wait_for_completion:
            task_result = self._wait_for_task(clean_task_id)
        else:
            task_result = self.seedance_client.get_task(clean_task_id)
            self._emit_status(task_result)
        updated = attach_seedance_render(validated_asset, task_result)
        if task_result.video_url:
            video_path = output_dir / "highlight_commerce_seedance.mp4"
            _download_video(task_result.video_url, video_path, http_client=self.http_client)
            updated["render"]["output_video_path"] = str(video_path)
        return updated

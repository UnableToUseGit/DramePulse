from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelines.highlight_commerce.generation import (
    HighlightCommerceCartoonPipeline,
    HighlightCommerceSeedancePipeline,
)
from pipelines.highlight_commerce.script_generation import (
    HighlightCommerceScriptGenerationPipeline,
    apply_highlight_commerce_script,
)


SCRIPT_FILENAME = "highlight_commerce_script.json"
CARTOON_ASSET_FILENAME = "highlight_commerce_cartoon_asset.json"
RESULT_FILENAME = "highlight_commerce_v2_result.json"
LEGACY_RENDER_FILENAME = "highlight_commerce_render.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _script_document_from_asset(asset: dict[str, Any]) -> dict[str, Any]:
    generated_script = asset.get("generated_script")
    if not isinstance(generated_script, dict):
        generated_script = {}
    return {
        "hook_strategy": generated_script.get("hook_strategy", ""),
        "storyboard": asset.get("storyboard", []),
        "product_mentions": generated_script.get("product_mentions", []),
        "avoid_claims": generated_script.get("avoid_claims", []),
        "seedance_prompt_notes": generated_script.get("seedance_prompt_notes", []),
    }


class HighlightCommerceV2Pipeline:
    def __init__(
        self,
        *,
        script_pipeline: Any | None = None,
        cartoon_pipeline: Any | None = None,
        seedance_pipeline: Any | None = None,
    ) -> None:
        self.script_pipeline = script_pipeline or HighlightCommerceScriptGenerationPipeline()
        self.cartoon_pipeline = cartoon_pipeline or HighlightCommerceCartoonPipeline()
        self.seedance_pipeline = seedance_pipeline or HighlightCommerceSeedancePipeline()

    def _scripted_asset(
        self,
        asset: dict[str, Any],
        *,
        output_dir: Path,
        script_path: Path | None,
        force_script: bool,
    ) -> dict[str, Any]:
        output_script_path = output_dir / SCRIPT_FILENAME
        if script_path is not None:
            script = _load_json(script_path)
            scripted_asset = apply_highlight_commerce_script(asset, script)
        elif output_script_path.exists() and not force_script:
            script = _load_json(output_script_path)
            scripted_asset = apply_highlight_commerce_script(asset, script)
        else:
            scripted_asset = self.script_pipeline.run(asset)
        _write_json(output_script_path, _script_document_from_asset(scripted_asset))
        return scripted_asset

    def _cartoon_asset(
        self,
        scripted_asset: dict[str, Any],
        *,
        output_dir: Path,
        force_cartoon_assets: bool,
        reuse_cartoon_assets: bool,
    ) -> dict[str, Any]:
        output_cartoon_path = output_dir / CARTOON_ASSET_FILENAME
        if reuse_cartoon_assets and output_cartoon_path.exists() and not force_cartoon_assets:
            return _load_json(output_cartoon_path)
        cartoon_asset = self.cartoon_pipeline.run(scripted_asset, output_dir=output_dir)
        _write_json(output_cartoon_path, cartoon_asset)
        return cartoon_asset

    def run(
        self,
        asset: dict[str, Any],
        *,
        output_dir: Path,
        script_path: Path | None = None,
        force_script: bool = False,
        force_cartoon_assets: bool = False,
        reuse_cartoon_assets: bool = True,
        resume_task_id: str | None = None,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        if resume_task_id:
            cartoon_asset_path = output_dir / CARTOON_ASSET_FILENAME
            if not cartoon_asset_path.exists():
                raise FileNotFoundError(
                    f"Cannot resume Seedance task without cartoon asset: {cartoon_asset_path}"
                )
            cartoon_asset = _load_json(cartoon_asset_path)
            result = self.seedance_pipeline.update_existing_task(
                cartoon_asset,
                task_id=resume_task_id,
                output_dir=output_dir,
            )
        else:
            scripted_asset = self._scripted_asset(
                asset,
                output_dir=output_dir,
                script_path=script_path,
                force_script=force_script,
            )
            cartoon_asset = self._cartoon_asset(
                scripted_asset,
                output_dir=output_dir,
                force_cartoon_assets=force_cartoon_assets,
                reuse_cartoon_assets=reuse_cartoon_assets,
            )
            result = self.seedance_pipeline.run(cartoon_asset, output_dir=output_dir)

        result = {
            **result,
            "pipeline_version": "highlight_commerce_v2",
        }
        _write_json(output_dir / RESULT_FILENAME, result)
        _write_json(output_dir / LEGACY_RENDER_FILENAME, result)
        return result

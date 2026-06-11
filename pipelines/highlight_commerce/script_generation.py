from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from pipelines.client import LlmClientProtocol, VolcArkLlmClient


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


def _source_assets(asset: dict[str, Any]) -> dict[str, Any]:
    return _require_dict(asset, "source_assets")


def _script_payload(raw: dict[str, Any]) -> dict[str, Any]:
    nested = raw.get("highlight_commerce_script")
    if isinstance(nested, dict):
        return nested
    return raw


def _asset_reference_images(asset: dict[str, Any]) -> list[Path]:
    source_assets = _source_assets(asset)
    keys = [
        "highlight_image_path",
        "male_character_image_path",
        "female_character_image_path",
        "product_image_path",
    ]
    paths: list[Path] = []
    for key in keys:
        path = Path(str(source_assets.get(key) or ""))
        if path.exists():
            paths.append(path)
    return paths


def _forbidden_claims(asset: dict[str, Any], script: dict[str, Any]) -> list[str]:
    product = _require_dict(asset, "product")
    claims = product.get("must_avoid", [])
    if not isinstance(claims, list):
        return []
    checked_payload = {
        "hook_strategy": script.get("hook_strategy"),
        "storyboard": script.get("storyboard"),
        "product_mentions": script.get("product_mentions"),
        "seedance_prompt_notes": script.get("seedance_prompt_notes"),
    }
    script_text = json.dumps(checked_payload, ensure_ascii=False)
    return [str(claim) for claim in claims if str(claim).strip() and str(claim) in script_text]


def validate_highlight_commerce_script(
    raw_script: dict[str, Any],
    *,
    asset: dict[str, Any],
) -> dict[str, Any]:
    script = _script_payload(raw_script)
    hook_strategy = _clean_text(script.get("hook_strategy"))
    if not hook_strategy:
        raise ValueError("Highlight commerce script requires `hook_strategy`")

    storyboard = script.get("storyboard")
    if not isinstance(storyboard, list) or len(storyboard) < 3:
        raise ValueError("Highlight commerce script requires at least 3 storyboard shots")

    target_duration = float(asset.get("target_duration_sec") or _request_plan(asset).get("duration") or 12)
    normalized_storyboard: list[dict[str, Any]] = []
    previous_end = -1.0
    for index, shot in enumerate(storyboard, start=1):
        if not isinstance(shot, dict):
            raise ValueError("Storyboard shots must be objects")
        shot_id = _clean_text(shot.get("shot_id")) or f"shot_{index:03d}"
        try:
            start_sec = float(shot.get("start_sec"))
            end_sec = float(shot.get("end_sec"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Storyboard shot {shot_id} requires numeric start_sec/end_sec") from exc
        if start_sec < 0 or end_sec <= start_sec or end_sec > target_duration + 0.5:
            raise ValueError(f"Storyboard shot {shot_id} has invalid timing")
        if start_sec < previous_end - 0.05:
            raise ValueError(f"Storyboard shot {shot_id} overlaps previous shot")
        previous_end = end_sec
        description = _clean_text(shot.get("description"))
        visual_prompt = _clean_text(shot.get("visual_prompt"))
        if not description or not visual_prompt:
            raise ValueError(f"Storyboard shot {shot_id} requires description and visual_prompt")

        raw_dialogue = shot.get("dialogue", [])
        if not isinstance(raw_dialogue, list):
            raise ValueError(f"Storyboard shot {shot_id}.dialogue must be a list")
        dialogue: list[dict[str, str]] = []
        for line in raw_dialogue:
            if not isinstance(line, dict):
                raise ValueError(f"Storyboard shot {shot_id}.dialogue entries must be objects")
            speaker = _clean_text(line.get("speaker"))
            text = _clean_text(line.get("text"))
            if not speaker or not text:
                raise ValueError(f"Storyboard shot {shot_id}.dialogue requires speaker and text")
            dialogue.append({"speaker": speaker, "text": text})

        normalized = dict(shot)
        normalized.update(
            {
                "shot_id": shot_id,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "description": description,
                "visual_prompt": visual_prompt,
                "dialogue": dialogue,
                "product_visibility": _clean_text(shot.get("product_visibility")) or "none",
            }
        )
        normalized_storyboard.append(normalized)

    product_mentions = script.get("product_mentions", [])
    if not isinstance(product_mentions, list) or not product_mentions:
        raise ValueError("Highlight commerce script requires non-empty product_mentions")

    seedance_prompt_notes = script.get("seedance_prompt_notes", [])
    if not isinstance(seedance_prompt_notes, list):
        raise ValueError("Highlight commerce script seedance_prompt_notes must be a list")

    normalized_script = dict(script)
    normalized_script["hook_strategy"] = hook_strategy
    normalized_script["storyboard"] = normalized_storyboard
    normalized_script["product_mentions"] = [_clean_text(item) for item in product_mentions if _clean_text(item)]
    normalized_script["avoid_claims"] = [
        _clean_text(item)
        for item in script.get("avoid_claims", [])
        if _clean_text(item)
    ]
    normalized_script["seedance_prompt_notes"] = [
        _clean_text(item)
        for item in seedance_prompt_notes
        if _clean_text(item)
    ]

    forbidden_claims = _forbidden_claims(asset, normalized_script)
    if forbidden_claims:
        raise ValueError(f"Highlight commerce script contains forbidden claim: {forbidden_claims[0]}")
    return normalized_script


def apply_highlight_commerce_script(
    asset: dict[str, Any],
    raw_script: dict[str, Any],
) -> dict[str, Any]:
    script = validate_highlight_commerce_script(raw_script, asset=asset)
    updated = deepcopy(asset)
    updated["storyboard"] = script["storyboard"]
    updated["generated_script"] = {
        "source": "llm",
        "hook_strategy": script["hook_strategy"],
        "product_mentions": script["product_mentions"],
        "avoid_claims": script.get("avoid_claims", []),
        "seedance_prompt_notes": script.get("seedance_prompt_notes", []),
    }
    plan = dict(_request_plan(updated))
    existing_notes = plan.get("prompt_notes", [])
    notes = list(existing_notes) if isinstance(existing_notes, list) else []
    notes.extend(script.get("seedance_prompt_notes", []))
    plan["prompt_notes"] = notes
    updated["seedance_request_plan"] = plan
    return updated


def _build_system_prompt() -> str:
    return (
        "You are a short-drama commerce creative director. "
        "Write a compact video ad script that starts from a drama highlight and naturally bridges to a product. "
        "Return only JSON."
    )


def _build_user_prompt(asset: dict[str, Any]) -> str:
    product = _require_dict(asset, "product")
    highlight = _require_dict(asset, "highlight")
    target_duration = asset.get("target_duration_sec") or _request_plan(asset).get("duration") or 12
    return "\n".join(
        [
            "Generate one highlight-commerce ad script JSON for Seedance.",
            "Creative requirements:",
            f"- Total duration must be {target_duration} seconds.",
            "- Use 4 to 6 shots with explicit start_sec/end_sec.",
            "- The first shot must continue the drama highlight, not start like an ad.",
            "- Use the male lead for a short natural reaction line when appropriate.",
            "- Use the female lead to bridge into the product and close the recommendation.",
            "- Product appearance must be motivated by the highlight scene.",
            "- Do not make medical, permanent, absolute, or exaggerated claims.",
            "- Keep dialogue concise and suitable for spoken video generation.",
            "- Return JSON in this shape:",
            '{ "highlight_commerce_script": { "hook_strategy": "...", "storyboard": [{ "shot_id": "shot_001_highlight_hook", "start_sec": 0.0, "end_sec": 2.0, "description": "...", "visual_prompt": "...", "dialogue": [{ "speaker": "male_lead", "text": "..." }], "product_visibility": "none|low|medium|high", "on_screen_text": ["..."] }], "product_mentions": ["..."], "avoid_claims": ["..."], "seedance_prompt_notes": ["..."] } }',
            "",
            "[HIGHLIGHT]",
            json.dumps(highlight, ensure_ascii=False),
            "[/HIGHLIGHT]",
            "",
            "[PRODUCT]",
            json.dumps(product, ensure_ascii=False),
            "[/PRODUCT]",
            "",
            "[CHARACTERS]",
            json.dumps(asset.get("characters", []), ensure_ascii=False),
            "[/CHARACTERS]",
        ]
    )


def _build_repair_prompt(
    *,
    asset: dict[str, Any],
    invalid_script: dict[str, Any],
    error: Exception,
) -> str:
    return "\n".join(
        [
            "Repair the JSON highlight-commerce script so it passes validation.",
            f"Validation error: {error}",
            "Keep the creative idea if possible, but remove invalid claims and fix structure/timing.",
            "Return only the repaired JSON object in the required shape.",
            "",
            "[ORIGINAL_ASSET]",
            json.dumps(asset, ensure_ascii=False),
            "[/ORIGINAL_ASSET]",
            "",
            "[INVALID_SCRIPT]",
            json.dumps(invalid_script, ensure_ascii=False),
            "[/INVALID_SCRIPT]",
        ]
    )


class HighlightCommerceScriptGenerationPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol | None = None,
        max_output_tokens: int = 3600,
    ) -> None:
        self.llm_client = llm_client or VolcArkLlmClient()
        self.max_output_tokens = max_output_tokens

    def run(self, asset: dict[str, Any]) -> dict[str, Any]:
        raw = self.llm_client.generate_json_multimodal(
            system_prompt=_build_system_prompt(),
            user_prompt=_build_user_prompt(asset),
            image_paths=_asset_reference_images(asset),
            max_tokens=self.max_output_tokens,
        )
        try:
            return apply_highlight_commerce_script(asset, raw)
        except ValueError as first_error:
            repaired = self.llm_client.generate_json_multimodal(
                system_prompt=_build_system_prompt(),
                user_prompt=_build_repair_prompt(
                    asset=asset,
                    invalid_script=raw,
                    error=first_error,
                ),
                image_paths=_asset_reference_images(asset),
                max_tokens=self.max_output_tokens,
            )
            return apply_highlight_commerce_script(asset, repaired)

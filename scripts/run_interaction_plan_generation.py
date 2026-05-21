from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pipelines.client import OpenAICompatibleLlmClient
from pipelines.interaction_plan_generation import InteractionPlanGenerationPipeline
from scripts.run_highlight_recognition import ResolvedVideoInputs, resolve_video_inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run interaction plan generation for one episode.")
    parser.add_argument("video_id", help="Video id in the form case1_ep01.")
    parser.add_argument("--data-root", type=Path, default=Path("data"), help="Root data directory.")
    parser.add_argument("--output-root", type=Path, default=Path("output"), help="Directory for outputs.")
    parser.add_argument(
        "--highlight-recognition-path",
        type=Path,
        default=None,
        help="Path to highlight_recognition.json. Defaults to output/<video_id>/highlight_recognition.json.",
    )
    return parser


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_highlight_assets(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Highlight recognition output not found: {path}")
    payload = _load_json(path)
    highlight_assets = payload.get("highlight_assets", [])
    if not isinstance(highlight_assets, list):
        raise ValueError(f"`highlight_assets` must be a list in {path}")
    return [item for item in highlight_assets if isinstance(item, dict)]


def _load_danmaku_items(source_json_path: Path) -> list[dict[str, object]]:
    payload = _load_json(source_json_path)
    danmaku_items = payload.get("danmaku", [])
    if not isinstance(danmaku_items, list):
        raise ValueError(f"`danmaku` must be a list in {source_json_path}")
    return [item for item in danmaku_items if isinstance(item, dict)]


def _default_highlight_recognition_path(*, output_root: Path, video_id: str) -> Path:
    return output_root / video_id / "highlight_recognition.json"


def _run_for_video(
    *,
    resolved: ResolvedVideoInputs,
    highlight_recognition_path: Path,
    pipeline: InteractionPlanGenerationPipeline,
) -> list[dict[str, object]]:
    highlight_assets = _load_highlight_assets(highlight_recognition_path)
    danmaku_items = _load_danmaku_items(resolved.source_json_path)
    return [
        pipeline.run(
            highlight_asset=highlight_asset,
            video_file_path=resolved.video_path,
            subtitle_file_path=resolved.subtitle_path,
            danmaku_items=danmaku_items,
        )
        for highlight_asset in highlight_assets
    ]


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: InteractionPlanGenerationPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    resolved = resolve_video_inputs(args.video_id, data_root=args.data_root)
    output_dir = args.output_root / args.video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    highlight_recognition_path = args.highlight_recognition_path or _default_highlight_recognition_path(
        output_root=args.output_root,
        video_id=args.video_id,
    )

    active_pipeline = pipeline or InteractionPlanGenerationPipeline(llm_client=OpenAICompatibleLlmClient())
    interaction_plans = _run_for_video(
        resolved=resolved,
        highlight_recognition_path=highlight_recognition_path,
        pipeline=active_pipeline,
    )

    payload = {
        "video_id": args.video_id,
        "video_path": str(resolved.video_path),
        "source_json_path": str(resolved.source_json_path),
        "subtitle_path": str(resolved.subtitle_path),
        "highlight_recognition_path": str(highlight_recognition_path),
        "interaction_plans": interaction_plans,
    }
    output_path = output_dir / "interaction_plan_generation.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

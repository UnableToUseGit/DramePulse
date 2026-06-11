from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.client import VolcArkLlmClient
from pipelines.highlight_commerce.generation import (
    DEFAULT_STYLE_REFERENCE_DIR,
    HighlightCommerceCartoonPipeline,
    HighlightCommerceSeedancePipeline,
)
from pipelines.highlight_commerce.script_generation import HighlightCommerceScriptGenerationPipeline
from pipelines.highlight_commerce.v2_pipeline import HighlightCommerceV2Pipeline, RESULT_FILENAME
from pipelines.highlight_commerce.seedance_generation import SeedanceClient, SeedanceTaskResult
from pipelines.highlight_commerce.seedream_generation import SeedreamImageGenerationClient
from scripts.transcription.env import get_env_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run highlight-commerce v2 pipeline.")
    parser.add_argument("--asset", type=Path, required=True, help="Path to v2 highlight commerce asset JSON.")
    parser.add_argument("--output-root", type=Path, default=Path("output/role-commerce-v2"), help="Output root.")
    parser.add_argument("--script", type=Path, default=None, help="Use an existing script JSON instead of generating one.")
    parser.add_argument("--force-script", action="store_true", help="Regenerate LLM script even if output script exists.")
    parser.add_argument("--force-cartoon-assets", action="store_true", help="Regenerate cartoon references.")
    parser.add_argument("--no-reuse-cartoon-assets", action="store_true", help="Do not reuse existing cartoon asset JSON.")
    parser.add_argument("--resume-task-id", default=None, help="Resume polling/downloading an existing Seedance task.")
    parser.add_argument("--wait", action="store_true", default=True, help="Wait for Seedance completion. Default: true.")
    parser.add_argument("--no-wait", action="store_true", help="Create task but do not wait for completion.")
    parser.add_argument("--poll-interval-sec", type=float, default=2.0)
    parser.add_argument("--max-poll-attempts", type=int, default=180)
    parser.add_argument("--style-reference-dir", type=Path, default=DEFAULT_STYLE_REFERENCE_DIR)
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file.")
    return parser


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _output_dir(output_root: Path, asset: dict[str, object]) -> Path:
    campaign_id = str(asset.get("campaign_id") or "").strip()
    if not campaign_id:
        raise ValueError("Highlight commerce asset requires `campaign_id`")
    return output_root / campaign_id


def _print_seedance_status(task_result: SeedanceTaskResult) -> None:
    message = f"Seedance task {task_result.task_id}: {task_result.status}"
    if task_result.video_url:
        message = f"{message} {task_result.video_url}"
    print(message, flush=True)


def build_pipeline(
    *,
    env_path: Path,
    style_reference_dir: Path,
    wait_for_completion: bool,
    poll_interval_sec: float,
    max_poll_attempts: int,
) -> HighlightCommerceV2Pipeline:
    llm_client = VolcArkLlmClient(
        api_key=get_env_value("ARK_API_KEY", env_path=env_path) or None,
        base_url=get_env_value("ARK_BASE_URL", env_path=env_path) or None,
        model_name=get_env_value("ARK_MODEL", env_path=env_path) or None,
    )
    seedream_client = SeedreamImageGenerationClient(
        api_key=get_env_value("ARK_API_KEY", env_path=env_path) or None,
        base_url=get_env_value("ARK_BASE_URL", env_path=env_path) or None,
        model_name=get_env_value("ARK_SEEDREAM_MODEL", env_path=env_path) or None,
    )
    seedance_client = SeedanceClient(
        api_key=get_env_value("ARK_API_KEY", env_path=env_path) or None,
        base_url=get_env_value("ARK_BASE_URL", env_path=env_path) or None,
    )
    return HighlightCommerceV2Pipeline(
        script_pipeline=HighlightCommerceScriptGenerationPipeline(llm_client=llm_client),
        cartoon_pipeline=HighlightCommerceCartoonPipeline(
            seedream_client=seedream_client,
            style_reference_dir=style_reference_dir,
        ),
        seedance_pipeline=HighlightCommerceSeedancePipeline(
            seedance_client=seedance_client,
            wait_for_completion=wait_for_completion,
            poll_interval_sec=poll_interval_sec,
            max_poll_attempts=max_poll_attempts,
            status_callback=_print_seedance_status,
        ),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: HighlightCommerceV2Pipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    asset = _load_json(args.asset)
    output_dir = _output_dir(args.output_root, asset)
    wait_for_completion = not args.no_wait
    active_pipeline = pipeline or build_pipeline(
        env_path=args.env_file,
        style_reference_dir=args.style_reference_dir,
        wait_for_completion=wait_for_completion,
        poll_interval_sec=args.poll_interval_sec,
        max_poll_attempts=args.max_poll_attempts,
    )
    result = active_pipeline.run(
        asset,
        output_dir=output_dir,
        script_path=args.script,
        force_script=args.force_script,
        force_cartoon_assets=args.force_cartoon_assets,
        reuse_cartoon_assets=not args.no_reuse_cartoon_assets,
        resume_task_id=args.resume_task_id,
    )
    result_path = output_dir / RESULT_FILENAME
    print(f"Wrote highlight commerce v2 result: {result_path}")
    render = result.get("render")
    if isinstance(render, dict):
        if render.get("provider_job_id"):
            print(f"Seedance task: {render['provider_job_id']}")
        if render.get("render_status"):
            print(f"Render status: {render['render_status']}")
        if render.get("output_video_path"):
            print(f"Downloaded video: {render['output_video_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

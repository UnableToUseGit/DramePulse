from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.highlight_commerce.generation import HighlightCommerceSeedancePipeline
from pipelines.highlight_commerce.seedance_generation import SeedanceClient, SeedanceTaskResult
from scripts.transcription.env import get_env_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render one highlight commerce clip with Seedance.")
    parser.add_argument("--asset", type=Path, required=True, help="Path to highlight commerce JSON.")
    parser.add_argument("--output-root", type=Path, default=Path("output/role-commerce-v2"), help="Output root.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file.")
    parser.add_argument("--no-wait", action="store_true", help="Create task but do not poll until completion.")
    parser.add_argument("--poll-interval-sec", type=float, default=2.0)
    parser.add_argument("--max-poll-attempts", type=int, default=120)
    return parser


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def build_seedance_client(*, env_path: Path | None = None) -> SeedanceClient:
    dotenv_api_key = get_env_value("ARK_API_KEY", env_path=env_path)
    dotenv_base_url = get_env_value("ARK_BASE_URL", env_path=env_path)
    return SeedanceClient(api_key=dotenv_api_key or None, base_url=dotenv_base_url or None)


def _print_seedance_status(task_result: SeedanceTaskResult) -> None:
    message = f"Seedance task {task_result.task_id}: {task_result.status}"
    if task_result.video_url:
        message = f"{message} {task_result.video_url}"
    print(message, flush=True)


def _output_dir(output_root: Path, asset: dict[str, object]) -> Path:
    campaign_id = str(asset.get("campaign_id") or "").strip()
    if not campaign_id:
        raise ValueError("Highlight commerce asset requires `campaign_id`")
    return output_root / campaign_id


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: HighlightCommerceSeedancePipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    asset = _load_json(args.asset)
    output_dir = _output_dir(args.output_root, asset)
    active_pipeline = pipeline or HighlightCommerceSeedancePipeline(
        seedance_client=build_seedance_client(env_path=args.env_file),
        wait_for_completion=not args.no_wait,
        poll_interval_sec=args.poll_interval_sec,
        max_poll_attempts=args.max_poll_attempts,
        status_callback=_print_seedance_status,
    )
    result = active_pipeline.run(asset, output_dir=output_dir)
    output_path = output_dir / "highlight_commerce_render.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote highlight commerce render: {output_path}")
    render = result.get("render")
    if isinstance(render, dict) and render.get("output_video_path"):
        print(f"Downloaded video: {render['output_video_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

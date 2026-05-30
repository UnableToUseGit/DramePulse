from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from pathlib import Path as _Path
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from pipelines.client import VolcArkLlmClient
from pipelines.expression_trigger_detection import expression_triggers_to_highlight_assets
from pipelines.highlight_recognition import HighlightRecognitionPipeline
from scripts.transcription.env import load_dotenv_values


class ResolvedVideoInputs:
    def __init__(self, video_id: str, video_path: Path, source_json_path: Path, subtitle_path: Path) -> None:
        self.video_id = video_id
        self.video_path = video_path
        self.source_json_path = source_json_path
        self.subtitle_path = subtitle_path


def resolve_video_inputs(video_id: str, *, data_root: Path) -> ResolvedVideoInputs:
    case_id, episode_id = video_id.rsplit("_", 1)
    case_dir = data_root / case_id
    video_path = case_dir / f"{episode_id}.mp4"
    source_json_path = case_dir / f"{episode_id}.json"
    subtitle_path = case_dir / f"{episode_id}.srt"
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not source_json_path.exists():
        raise FileNotFoundError(f"Source JSON not found: {source_json_path}")
    if not subtitle_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
    return ResolvedVideoInputs(
        video_id=video_id,
        video_path=video_path,
        source_json_path=source_json_path,
        subtitle_path=subtitle_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run highlight recognition for one episode.")
    parser.add_argument("video_id", help="Video id in the form case1_ep01.")
    parser.add_argument("--data-root", type=Path, default=Path("data"), help="Root data directory.")
    parser.add_argument("--output-root", type=Path, default=Path("output"), help="Directory for outputs.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument(
        "--include-finale-trigger",
        action="store_true",
        help="Enable finale quality-judgment trigger detection for known final episodes.",
    )
    return parser


def build_ark_client(*, env_path: Path | None = None) -> VolcArkLlmClient:
    dotenv_values = load_dotenv_values(env_path)
    dotenv_api_key = dotenv_values.get("ARK_API_KEY") or os.environ.get("ARK_API_KEY")
    dotenv_base_url = dotenv_values.get("ARK_BASE_URL") or os.environ.get("ARK_BASE_URL")
    dotenv_model = dotenv_values.get("ARK_MODEL") or os.environ.get("ARK_MODEL")
    return VolcArkLlmClient(
        api_key=dotenv_api_key or None,
        base_url=dotenv_base_url or None,
        model_name=dotenv_model or None,
    )


def _load_source_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_danmaku_items(source_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = source_payload.get("danmaku", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _extract_video_metadata(source_payload: dict[str, Any]) -> dict[str, Any]:
    metadata_keys = (
        "title",
        "description",
        "series_name",
        "episode_label",
        "episode_no",
        "source_url",
        "duration_ms",
    )
    return {key: source_payload[key] for key in metadata_keys if key in source_payload}


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: HighlightRecognitionPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    resolved = resolve_video_inputs(args.video_id, data_root=args.data_root)

    output_dir = args.output_root / args.video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    active_pipeline = pipeline or HighlightRecognitionPipeline(llm_client=build_ark_client(env_path=args.env_file))
    source_payload = _load_source_payload(resolved.source_json_path)
    metadata = _extract_video_metadata(source_payload)
    danmaku_items = _extract_danmaku_items(source_payload)
    if hasattr(active_pipeline, "run_expression_triggers"):
        expression_triggers = active_pipeline.run_expression_triggers(
            video_id=args.video_id,
            video_file_path=resolved.video_path,
            subtitle_file_path=resolved.subtitle_path,
            metadata=metadata,
            danmaku_items=danmaku_items,
            include_finale_trigger=args.include_finale_trigger,
        )
        highlight_assets = expression_triggers_to_highlight_assets(expression_triggers)
    else:
        expression_triggers = []
        highlight_assets = active_pipeline.run(
            video_id=args.video_id,
            video_file_path=resolved.video_path,
            subtitle_file_path=resolved.subtitle_path,
        )

    payload = {
        "video_id": args.video_id,
        "video_path": str(resolved.video_path),
        "source_json_path": str(resolved.source_json_path),
        "subtitle_path": str(resolved.subtitle_path),
        "expression_triggers": expression_triggers,
        "highlight_assets": highlight_assets,
    }
    output_path = output_dir / "highlight_recognition.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

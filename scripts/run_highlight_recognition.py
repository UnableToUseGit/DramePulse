from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pipelines.client import OpenAICompatibleLlmClient
from pipelines.highlight_recognition import HighlightRecognitionPipeline


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
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: HighlightRecognitionPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    resolved = resolve_video_inputs(args.video_id, data_root=args.data_root)

    output_dir = args.output_root / args.video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    active_pipeline = pipeline or HighlightRecognitionPipeline(llm_client=OpenAICompatibleLlmClient())
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
        "highlight_assets": highlight_assets,
    }
    output_path = output_dir / "highlight_recognition.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

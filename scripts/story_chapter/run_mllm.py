from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.story_chapter.baseline_mllm import StoryChapterMultimodalPipeline
from scripts.story_chapter.run_text import build_ark_client, load_video_metadata_from_scene_detection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run multimodal story chapter generation for one episode.")
    parser.add_argument("video_id", help="Video id used for output directory and prompts.")
    parser.add_argument("--video", type=Path, required=True, help="Path to video.mp4.")
    parser.add_argument("--transcription", type=Path, required=True, help="Path to *.transcription.json.")
    parser.add_argument("--scene-detection", type=Path, required=True, help="Path to scene_detection.json for metadata duration.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/story_chapter_multimodal_validation"),
        help="Directory for outputs.",
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument("--frame-interval-seconds", type=float, default=1.0, help="Initial frame sampling interval in seconds.")
    parser.add_argument("--max-frames", type=int, default=120, help="Uniformly downsample sampled frames to this limit.")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: StoryChapterMultimodalPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    active_pipeline = pipeline or StoryChapterMultimodalPipeline(
        llm_client=build_ark_client(env_path=args.env_file),
        frame_interval_seconds=args.frame_interval_seconds,
        max_frames=args.max_frames,
    )
    output_path = active_pipeline.run(
        video_id=args.video_id,
        video_path=args.video,
        video_metadata=load_video_metadata_from_scene_detection(args.scene_detection),
        transcription_path=args.transcription,
        output_root=args.output_root,
    )
    print(f"Wrote multimodal story chapters: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

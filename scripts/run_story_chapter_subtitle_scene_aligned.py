from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.factory import build_llm_client
from pipelines.story_chapter.subtitle_scene_aligned import StoryChapterSubtitleSceneAlignedPipeline
from scripts.run_story_chapter_generation import load_video_metadata_from_scene_detection


def print_progress(message: str) -> None:
    print(message, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run subtitle-first, scene-aligned story chapter workflow for one episode.")
    parser.add_argument("video_id", help="Video id used for output directory and prompts.")
    parser.add_argument("--video", type=Path, required=True, help="Path to video.mp4.")
    parser.add_argument("--transcription", type=Path, required=True, help="Path to *.transcription.json.")
    parser.add_argument("--scene-detection", type=Path, required=True, help="Path to scene_detection.json.")
    parser.add_argument("--output-root", type=Path, default=Path("output/story_chapter_subtitle_scene_aligned_validation"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument("--draft-frame-interval-seconds", type=float, default=10.0, help="Sparse frame interval for the first draft LLM call. Use 0 to disable.")
    parser.add_argument("--max-alignment-window-seconds", type=float, default=10.0)
    parser.add_argument("--min-chapter-seconds", type=float, default=12.0)
    return parser


def build_pipeline(args: argparse.Namespace) -> StoryChapterSubtitleSceneAlignedPipeline:
    llm_client = build_llm_client(env_path=args.env_file)
    return StoryChapterSubtitleSceneAlignedPipeline(
        llm_client=llm_client,
        draft_frame_interval_seconds=args.draft_frame_interval_seconds,
        max_alignment_window_seconds=args.max_alignment_window_seconds,
        min_chapter_seconds=args.min_chapter_seconds,
        progress_logger=print_progress,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: StoryChapterSubtitleSceneAlignedPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    active_pipeline = pipeline or build_pipeline(args)
    output_path = active_pipeline.run(
        video_id=args.video_id,
        video_path=args.video,
        video_metadata=load_video_metadata_from_scene_detection(args.scene_detection),
        transcription_path=args.transcription,
        scene_detection_path=args.scene_detection,
        output_root=args.output_root,
    )
    print(f"Wrote subtitle-scene aligned story chapters: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

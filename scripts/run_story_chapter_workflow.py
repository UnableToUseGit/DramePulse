from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.factory import build_llm_client
from pipelines.story_chapter.workflow import StoryChapterWorkflowPipeline
from scripts.run_story_chapter_generation import load_video_metadata_from_scene_detection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run story chapter workflow for one episode.")
    parser.add_argument("video_id", help="Video id used for output directory and prompts.")
    parser.add_argument("--video", type=Path, required=True, help="Path to video.mp4.")
    parser.add_argument("--transcription", type=Path, required=True, help="Path to *.transcription.json.")
    parser.add_argument("--scene-detection", type=Path, required=True, help="Path to scene_detection.json.")
    parser.add_argument("--output-root", type=Path, default=Path("output/story_chapter_workflow_validation"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument("--top-candidates", type=int, default=16)
    parser.add_argument("--candidate-frame-offset-seconds", type=float, nargs="+", default=[-1.0, 0.0, 1.0])
    parser.add_argument("--frame-max-height", type=int, default=512)
    return parser


def build_pipeline(args: argparse.Namespace) -> StoryChapterWorkflowPipeline:
    llm_client = build_llm_client(env_path=args.env_file)
    return StoryChapterWorkflowPipeline(
        text_llm_client=llm_client,
        mllm_client=llm_client,
        top_candidates=args.top_candidates,
        candidate_frame_offsets_seconds=args.candidate_frame_offset_seconds,
        frame_max_height=args.frame_max_height,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: StoryChapterWorkflowPipeline | None = None,
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
    print(f"Wrote story chapter workflow output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

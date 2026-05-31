from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.story_chapter_generation import StoryChapterPipeline
from scripts.transcription.env import get_env_value


def build_ark_client(*, env_path: Path | None = None):
    from pipelines.client import VolcArkLlmClient

    dotenv_api_key = get_env_value("ARK_API_KEY", env_path=env_path)
    dotenv_base_url = get_env_value("ARK_BASE_URL", env_path=env_path)
    dotenv_model = get_env_value("ARK_MODEL", env_path=env_path)
    return VolcArkLlmClient(
        api_key=dotenv_api_key or None,
        base_url=dotenv_base_url or None,
        model_name=dotenv_model or None,
    )


def load_video_metadata_from_scene_detection(scene_detection_path: Path) -> dict[str, Any]:
    payload = json.loads(scene_detection_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Scene detection payload must be an object: {scene_detection_path}")
    duration = payload.get("duration_seconds") or payload.get("duration")
    if duration is None:
        scenes = payload.get("scenes")
        if isinstance(scenes, list):
            end_times = [
                float(scene["end_time"])
                for scene in scenes
                if isinstance(scene, dict) and isinstance(scene.get("end_time"), int | float)
            ]
            duration = max(end_times) if end_times else None
    if duration is None:
        raise ValueError(f"Cannot infer video duration from scene detection: {scene_detection_path}")
    return {"duration_seconds": float(duration)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run subtitle-based story chapter generation and scene snapping.")
    parser.add_argument("video_id", help="Video id used for output directory and prompts.")
    parser.add_argument("--transcription", type=Path, required=True, help="Path to *.transcription.json.")
    parser.add_argument("--scene-detection", type=Path, required=True, help="Path to scene_detection.json.")
    parser.add_argument("--output-root", type=Path, default=Path("output"), help="Directory for outputs.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: StoryChapterPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    active_pipeline = pipeline or StoryChapterPipeline(
        llm_client=build_ark_client(env_path=args.env_file),
    )
    output_path = active_pipeline.run(
        video_id=args.video_id,
        video_metadata=load_video_metadata_from_scene_detection(args.scene_detection),
        transcription_path=args.transcription,
        scene_detection_path=args.scene_detection,
        output_root=args.output_root,
    )
    print(f"Wrote story chapters: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

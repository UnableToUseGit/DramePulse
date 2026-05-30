from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.highlight_candidate_generation import HighlightCandidatePipeline
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run text-stage highlight cue recall and scene mapping.")
    parser.add_argument("video_id", help="Video id used for output directory and prompts.")
    parser.add_argument("--transcription", type=Path, required=True, help="Path to *.transcription.json.")
    parser.add_argument("--scene-detection", type=Path, required=True, help="Path to scene_detection.json.")
    parser.add_argument("--output-root", type=Path, default=Path("output"), help="Directory for outputs.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument("--context-size", type=int, default=1, help="Neighboring scenes to include around the target scene.")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: HighlightCandidatePipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    active_pipeline = pipeline or HighlightCandidatePipeline(
        llm_client=build_ark_client(env_path=args.env_file),
        context_size=args.context_size,
    )
    output_path = active_pipeline.run(
        video_id=args.video_id,
        transcription_path=args.transcription,
        scene_detection_path=args.scene_detection,
        output_root=args.output_root,
    )
    print(f"Wrote highlight candidates: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_text_expression_trigger_detection_batch import build_parser, build_pipeline, main, write_episode_output

__all__ = [
    "build_parser",
    "build_pipeline",
    "main",
    "write_episode_output",
]


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_expression_trigger_text_baseline_batch import build_parser, build_pipeline, main, write_episode_output

__all__ = [
    "build_parser",
    "build_pipeline",
    "main",
    "write_episode_output",
]


if __name__ == "__main__":
    raise SystemExit(main())

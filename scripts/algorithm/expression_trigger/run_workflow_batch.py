from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_workflow_expression_trigger_detection_batch import (
    DEFAULT_OUTPUT_ROOT,
    build_parser,
    build_pipeline,
    main,
    print_workflow_progress,
    write_workflow_episode_output,
)

__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "build_parser",
    "build_pipeline",
    "main",
    "print_workflow_progress",
    "write_workflow_episode_output",
]


if __name__ == "__main__":
    raise SystemExit(main())

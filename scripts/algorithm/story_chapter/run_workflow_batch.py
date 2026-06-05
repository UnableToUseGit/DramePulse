from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_story_chapter_workflow_batch import (
    WorkflowStoryChapterInput,
    build_parser,
    discover_workflow_inputs,
    main,
)

__all__ = [
    "WorkflowStoryChapterInput",
    "build_parser",
    "discover_workflow_inputs",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.story_chapter.run_text_batch import (
    DEFAULT_DATASET_ROOT,
    StoryChapterInput,
    build_parser,
    discover_story_chapter_inputs,
    main,
)

__all__ = [
    "DEFAULT_DATASET_ROOT",
    "StoryChapterInput",
    "build_parser",
    "discover_story_chapter_inputs",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

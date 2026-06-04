from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_story_chapter_generation_multimodal_batch import (
    MultimodalStoryChapterInput,
    build_parser,
    discover_multimodal_inputs,
    main,
)

__all__ = [
    "MultimodalStoryChapterInput",
    "build_parser",
    "discover_multimodal_inputs",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_story_chapter_generation_multimodal import build_parser, main

__all__ = [
    "build_parser",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

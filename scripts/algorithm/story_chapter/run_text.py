from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_story_chapter_generation import (
    build_ark_client,
    build_parser,
    load_video_metadata_from_scene_detection,
    main,
)

__all__ = [
    "build_ark_client",
    "build_parser",
    "load_video_metadata_from_scene_detection",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_inner_voice_danmaku_generation import (
    DEFAULT_OUTPUT_ROOT,
    build_parser,
    main,
    print_inner_voice_progress,
    write_inner_voice_output,
)

__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "build_parser",
    "main",
    "print_inner_voice_progress",
    "write_inner_voice_output",
]


if __name__ == "__main__":
    raise SystemExit(main())

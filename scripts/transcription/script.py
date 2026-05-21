from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Sequence

from .runner import transcribe_video_to_srt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transcribe a video into an SRT subtitle file.")
    parser.add_argument("video_path", type=Path, help="Path to the source video file.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to write the generated SRT file.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., Path] = transcribe_video_to_srt,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    runner(video_path=args.video_path, output_path=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

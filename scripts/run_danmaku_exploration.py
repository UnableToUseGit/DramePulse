from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.danmaku_exploration import explore_danmaku_csv, write_danmaku_exploration_output


DEFAULT_CSV_PATH = Path("data/圈选剧前5集弹幕.csv")
DEFAULT_OUTPUT_ROOT = Path("output/danmaku_exploration")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explore danmaku resonance and inner voice review candidates.")
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--window-sec", type=float, default=8.0)
    parser.add_argument("--step-sec", type=float, default=2.0)
    parser.add_argument("--min-window-danmaku-count", type=int, default=4)
    parser.add_argument("--max-windows-per-episode", type=int, default=50)
    parser.add_argument("--duration-sec", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = explore_danmaku_csv(
        args.csv_path,
        window_sec=args.window_sec,
        step_sec=args.step_sec,
        min_window_danmaku_count=args.min_window_danmaku_count,
        max_windows_per_episode=args.max_windows_per_episode,
        duration_sec=args.duration_sec,
    )
    paths = write_danmaku_exploration_output(output_root=args.output_root, payload=payload)
    print(
        "Wrote danmaku exploration: "
        f"episodes={len(payload['episode_profiles'])} "
        f"windows={len(payload['resonance_windows'])} "
        f"candidates={len(payload['inner_voice_review_candidates'])} "
        f"output_root={args.output_root}"
    )
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

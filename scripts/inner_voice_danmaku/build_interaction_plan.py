from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.inner_voice_danmaku.interaction_plan import (
    build_inner_voice_interaction_plan,
    load_inner_voice_selection_payload,
    write_interaction_plan_output,
)

DEFAULT_SELECTION_PATH = Path("output/danmaku_exploration/inner_voice_selection_beiwang_ep01.json")
DEFAULT_OUTPUT_PATH = Path("output/danmaku_exploration/interaction_plan_beiwang_ep01.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build final inner voice danmaku interaction plan assets.")
    parser.add_argument("--selection-path", type=Path, default=DEFAULT_SELECTION_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--series-id", default="beiwang")
    parser.add_argument("--episode-id", default="ep01")
    parser.add_argument("--min-duration-sec", type=float, default=5.0)
    parser.add_argument("--max-duration-sec", type=float, default=8.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selection_payload = load_inner_voice_selection_payload(args.selection_path)
    plan = build_inner_voice_interaction_plan(
        selection_payload,
        series_id=args.series_id,
        episode_id=args.episode_id,
        min_duration_sec=args.min_duration_sec,
        max_duration_sec=args.max_duration_sec,
    )
    write_interaction_plan_output(output_path=args.output_path, plan=plan)
    print(
        "Wrote inner voice interaction plan: "
        f"items={len(plan)} "
        f"output={args.output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.factory import build_llm_client
from pipelines.danmaku_llm_refinement import (
    load_windows_payload,
    refine_danmaku_windows_with_llm,
    write_llm_candidates_output,
)


DEFAULT_WINDOWS_PATH = Path("output/danmaku_exploration/resonance_windows.json")
DEFAULT_OUTPUT_PATH = Path("output/danmaku_exploration/inner_voice_llm_candidates.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use LLM to identify semantic danmaku clusters for inner voice candidates.")
    parser.add_argument("--windows-path", type=Path, default=DEFAULT_WINDOWS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--duration-sec", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None, *, llm_client: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_client = llm_client or build_llm_client(env_path=args.env_file)
    windows_payload = load_windows_payload(args.windows_path)
    result = refine_danmaku_windows_with_llm(
        windows_payload,
        llm_client=active_client,
        max_tokens=args.max_tokens,
        duration_sec=args.duration_sec,
    )
    write_llm_candidates_output(output_path=args.output_path, payload=result)
    print(
        "Wrote danmaku LLM refinement: "
        f"windows={result['llmWindowCount']} "
        f"candidates={result['candidateCount']} "
        f"output={args.output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

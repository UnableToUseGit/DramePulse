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
    parser.add_argument("--series-id", help="Only process windows whose video_id starts with this series id.")
    parser.add_argument("--episode-id", help="Only process windows whose video_id ends with this episode id.")
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--duration-sec", type=float, default=5.0)
    return parser


def filter_windows_payload(
    payload: dict[str, Any],
    *,
    series_id: str | None = None,
    episode_id: str | None = None,
) -> dict[str, Any]:
    raw_windows = payload.get("windows")
    windows_key = "windows"
    if not isinstance(raw_windows, list):
        raw_windows = payload.get("resonance_windows")
        windows_key = "resonance_windows"
    if not isinstance(raw_windows, list):
        return dict(payload)

    filtered_windows: list[dict[str, Any]] = []
    for window in raw_windows:
        if not isinstance(window, dict):
            continue
        video_id = str(window.get("video_id") or window.get("videoId") or "")
        if series_id and not video_id.startswith(f"{series_id}_"):
            continue
        if episode_id and not video_id.endswith(f"_{episode_id}"):
            continue
        filtered_windows.append(window)

    filtered_payload = dict(payload)
    filtered_payload[windows_key] = filtered_windows
    return filtered_payload


def print_llm_refinement_progress(event: str, payload: dict[str, Any]) -> None:
    if event == "prepared":
        print(f"prepared: windows={payload.get('window_count', 0)}")
        return
    if event == "llm_window_start":
        video_id = payload.get("video_id") or "unknown"
        print(
            f"[{video_id}] llm_window_start: "
            f"{payload.get('window_index', 0)}/{payload.get('window_count', 0)} "
            f"window={payload.get('window_id')} "
            f"comments={payload.get('comment_count', 0)}"
        )
        return
    if event == "llm_window_done":
        video_id = payload.get("video_id") or "unknown"
        print(
            f"[{video_id}] llm_window_done: "
            f"{payload.get('window_index', 0)}/{payload.get('window_count', 0)} "
            f"window={payload.get('window_id')} "
            f"candidates={payload.get('candidate_count', 0)} "
            f"filtered={payload.get('filtered_count', 0)}"
        )
        return
    if event == "completed":
        print(
            f"completed: windows={payload.get('window_count', 0)} "
            f"candidates={payload.get('candidate_count', 0)} "
            f"filtered={payload.get('filtered_count', 0)}"
        )
        return
    print(f"{event}: {payload}")


def main(argv: Sequence[str] | None = None, *, llm_client: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_client = llm_client or build_llm_client(env_path=args.env_file)
    windows_payload = filter_windows_payload(
        load_windows_payload(args.windows_path),
        series_id=args.series_id,
        episode_id=args.episode_id,
    )
    result = refine_danmaku_windows_with_llm(
        windows_payload,
        llm_client=active_client,
        max_tokens=args.max_tokens,
        duration_sec=args.duration_sec,
        progress_callback=print_llm_refinement_progress,
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

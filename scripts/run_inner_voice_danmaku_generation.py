from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.algorithm_danmaku_csv import load_danmaku_csv_items
from scripts.run_expression_trigger_detection_batch import (
    DEFAULT_DATA_ROOT,
    build_llm_client,
    discover_episodes,
    extract_danmaku_items,
    load_source_payload,
)


DEFAULT_OUTPUT_ROOT = Path("output/inner_voice_danmaku")


def _format_optional_number(value: Any, *, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def print_inner_voice_progress(event: str, payload: dict[str, Any]) -> None:
    video_id = str(payload.get("video_id") or "unknown")
    if event == "prepared":
        print(
            f"[{video_id}] prepared: "
            f"source_danmaku={payload.get('source_danmaku_count', 0)} "
            f"clean_danmaku={payload.get('clean_danmaku_count', 0)}"
        )
        return
    if event == "windows_built":
        print(f"[{video_id}] windows_built: windows={payload.get('candidate_window_count', 0)}")
        return
    if event == "candidates_built":
        print(
            f"[{video_id}] candidates_built: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"filtered={payload.get('filtered_candidate_count', 0)} "
            f"llm_calls={payload.get('llm_call_count', 0)}"
        )
        return
    if event == "completed":
        print(f"[{video_id}] completed: cues={payload.get('selected_cue_count', 0)}")
        return
    print(f"[{video_id}] {event}: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}")


def build_pipeline(
    *,
    env_path: Path,
    enable_llm_semantic: bool,
    window_sec: float,
    step_sec: float,
    min_window_danmaku_count: int,
    min_unique_text_count: int,
    min_window_score: float,
    max_cues_per_episode: int,
    duration_sec: float,
    min_cue_gap_sec: float,
    llm_max_tokens: int,
):
    from pipelines.inner_voice_danmaku_generation import InnerVoiceDanmakuPipeline

    return InnerVoiceDanmakuPipeline(
        llm_client=build_llm_client(env_path=env_path) if enable_llm_semantic else None,
        enable_llm_semantic=enable_llm_semantic,
        window_sec=window_sec,
        step_sec=step_sec,
        min_window_danmaku_count=min_window_danmaku_count,
        min_unique_text_count=min_unique_text_count,
        min_window_score=min_window_score,
        max_cues_per_episode=max_cues_per_episode,
        duration_sec=duration_sec,
        min_cue_gap_sec=min_cue_gap_sec,
        llm_max_tokens=llm_max_tokens,
        progress_callback=print_inner_voice_progress,
    )


def _load_episode_danmaku(*, data_root: Path, series_id: str, episode_id: str, source_json_path: Path | None) -> list[dict[str, Any]]:
    csv_items = load_danmaku_csv_items(data_root, series_id=series_id, episode_id=episode_id)
    if csv_items:
        return csv_items
    return extract_danmaku_items(load_source_payload(source_json_path))


def write_inner_voice_output(*, output_root: Path, payload: dict[str, Any]) -> Path:
    video_id = str(payload["videoId"])
    output_dir = output_root / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    cues_path = output_dir / "inner_voice_cues.json"
    debug_path = output_dir / "inner_voice_debug.json"
    cues_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    debug_payload = payload.get("debug")
    if not isinstance(debug_payload, dict):
        debug_payload = {}
    debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cues_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate inner voice danmaku cues from real danmaku resonance windows.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--series-id", nargs="+", action="append")
    parser.add_argument("--episode-id", nargs="+", action="append")
    parser.add_argument("--video-id", nargs="+", action="append")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--enable-llm-semantic", action="store_true")
    parser.add_argument("--window-sec", type=float, default=8.0)
    parser.add_argument("--step-sec", type=float, default=2.0)
    parser.add_argument("--min-window-danmaku-count", type=int, default=4)
    parser.add_argument("--min-unique-text-count", type=int, default=2)
    parser.add_argument("--min-window-score", type=float, default=6.0)
    parser.add_argument("--max-cues-per-episode", type=int, default=8)
    parser.add_argument("--duration-sec", type=float, default=5.0)
    parser.add_argument("--min-cue-gap-sec", type=float, default=12.0)
    parser.add_argument("--llm-max-tokens", type=int, default=1200)
    return parser


def main(argv: Sequence[str] | None = None, *, pipeline: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    series_ids = [series_id for group in (args.series_id or []) for series_id in group]
    episode_ids = [episode_id for group in (args.episode_id or []) for episode_id in group]
    video_ids = [video_id for group in (args.video_id or []) for video_id in group]
    episodes = discover_episodes(
        data_root=args.data_root,
        series_ids=series_ids,
        episode_ids=episode_ids,
        video_ids=video_ids,
        limit=args.limit,
    )
    active_pipeline = pipeline or build_pipeline(
        env_path=args.env_file,
        enable_llm_semantic=args.enable_llm_semantic,
        window_sec=args.window_sec,
        step_sec=args.step_sec,
        min_window_danmaku_count=args.min_window_danmaku_count,
        min_unique_text_count=args.min_unique_text_count,
        min_window_score=args.min_window_score,
        max_cues_per_episode=args.max_cues_per_episode,
        duration_sec=args.duration_sec,
        min_cue_gap_sec=args.min_cue_gap_sec,
        llm_max_tokens=args.llm_max_tokens,
    )

    processed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    for episode in episodes:
        output_path = args.output_root / episode.video_id / "inner_voice_cues.json"
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"SKIP {episode.video_id}: existing {output_path}")
            continue
        print(f"RUN  {episode.video_id}")
        try:
            danmaku_items = _load_episode_danmaku(
                data_root=args.data_root,
                series_id=episode.series_id,
                episode_id=episode.episode_id,
                source_json_path=episode.source_json_path,
            )
            result = active_pipeline.run(
                video_id=episode.video_id,
                series_id=episode.series_id,
                episode_id=episode.episode_id,
                danmaku_items=danmaku_items,
            )
            written_path = write_inner_voice_output(output_root=args.output_root, payload=result)
            processed += 1
            print(f"WROTE {episode.video_id}: {written_path}")
        except Exception as exc:  # noqa: BLE001 - batch jobs should continue and report all failures.
            failed.append((episode.video_id, str(exc)))
            print(f"FAIL {episode.video_id}: {exc}")

    print(f"Done. processed={processed} skipped={skipped} failed={len(failed)} output_root={args.output_root}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

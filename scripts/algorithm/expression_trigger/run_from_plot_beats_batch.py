from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pipelines.client.factory import build_llm_client
from pipelines.expression_trigger.from_plot_beats import PlotBeatTriggerabilityPipeline
from scripts.algorithm.common import DEFAULT_DATA_ROOT, discover_episodes, now_iso, write_failure_diagnostics


DEFAULT_PLOT_BEAT_ROOT = Path("output/plot_beat/chapter_aligned")
DEFAULT_OUTPUT_ROOT = Path("output/expression_trigger_from_plot_beats")
ASSET_FILENAME = "expression_triggers.json"
DEBUG_FILENAME = "expression_triggers.debug.json"


def _format_optional_number(value: Any, *, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def print_from_plot_beats_progress(event: str, payload: dict[str, Any]) -> None:
    video_id = str(payload.get("video_id") or "unknown")
    if event == "prepared":
        print(
            f"[{video_id}] prepared: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"subtitles={payload.get('subtitle_segment_count', 0)} "
            f"duration={_format_optional_number(payload.get('duration_sec'), suffix='s')}"
        )
        return
    if event == "triggerability_start":
        print(
            f"[{video_id}] triggerability_start: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"top_k={payload.get('top_k')} "
            f"min_gap={payload.get('min_gap_seconds')}s "
            f"max_tokens={payload.get('max_tokens')}"
        )
        return
    if event == "triggerability_done":
        print(
            f"[{video_id}] triggerability_done: "
            f"decisions={payload.get('candidate_decision_count', 0)} "
            f"triggers={payload.get('trigger_count', 0)} "
            f"elapsed={_format_optional_number(payload.get('elapsed_sec'), suffix='s')} "
            f"tokens={_format_optional_number(payload.get('total_tokens'))}"
        )
        return
    if event == "completed":
        print(
            f"[{video_id}] completed: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"decisions={payload.get('candidate_decision_count', 0)} "
            f"triggers={payload.get('trigger_count', 0)}"
        )
        return
    print(f"[{video_id}] {event}: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run Expression Trigger from raw Plot Beat outputs.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--plot-beat-root", type=Path, default=DEFAULT_PLOT_BEAT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--series-id", nargs="+", action="append", help="Only process selected series ids.")
    parser.add_argument("--episode-id", nargs="+", action="append", help="Only process selected episode ids such as ep01.")
    parser.add_argument("--video-id", nargs="+", action="append", help="Only process exact video ids such as beiwang_ep01.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="Regenerate outputs that already exist.")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--min-gap-seconds", type=float, default=30.0)
    parser.add_argument("--max-output-tokens", type=int, default=6000)
    return parser


def _flatten_groups(groups: list[list[str]] | None) -> list[str]:
    return [item for group in (groups or []) for item in group]


def _plot_beats_path(plot_beat_root: Path, video_id: str) -> Path:
    return plot_beat_root / video_id / "plot_beats.json"


def _asset_output_path(output_root: Path, video_id: str) -> Path:
    return output_root / video_id / ASSET_FILENAME


def _debug_output_path(output_root: Path, video_id: str) -> Path:
    return output_root / video_id / DEBUG_FILENAME


def _asset_trigger(trigger: dict[str, Any]) -> dict[str, Any]:
    return {
        "trigger_id": str(trigger.get("trigger_id") or ""),
        "start_time": float(trigger.get("start_time", 0.0)),
        "end_time": float(trigger.get("end_time", 0.0)),
        "trigger_time": float(trigger.get("trigger_time", 0.0)),
        "expression_type": str(trigger.get("expression_type") or ""),
        "importance_score": float(trigger.get("importance_score", 0.0)),
        "summary": str(trigger.get("summary") or ""),
        "reason": str(trigger.get("reason") or ""),
    }


def write_from_plot_beats_output(*, result: Any, output_root: Path) -> Path:
    asset_path = _asset_output_path(output_root, str(result.video_id))
    debug_path = _debug_output_path(output_root, str(result.video_id))
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = str(result.created_at or now_iso())
    asset_payload = {
        "video_id": result.video_id,
        "series_id": result.series_id,
        "created_at": created_at,
        "expression_triggers": [_asset_trigger(trigger) for trigger in result.expression_triggers],
    }
    debug_payload = {
        "video_id": result.video_id,
        "series_id": result.series_id,
        "created_at": created_at,
        "pipeline_type": "plot_beat_triggerability",
        "plot_candidates": result.plot_candidates,
        "triggerability_decisions": result.triggerability_decisions,
        "expression_triggers": result.expression_triggers,
        "llm_calls": result.llm_calls,
    }
    asset_path.write_text(json.dumps(asset_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return asset_path


def build_pipeline(args: argparse.Namespace) -> PlotBeatTriggerabilityPipeline:
    return PlotBeatTriggerabilityPipeline(
        llm_client=build_llm_client(env_path=args.env_file),
        top_k=args.top_k,
        min_gap_seconds=args.min_gap_seconds,
        max_output_tokens=args.max_output_tokens,
        progress_callback=print_from_plot_beats_progress,
    )


def main(argv: Sequence[str] | None = None, *, pipeline: Any | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    episodes = discover_episodes(
        data_root=args.data_root,
        series_ids=_flatten_groups(args.series_id),
        episode_ids=_flatten_groups(args.episode_id),
        video_ids=_flatten_groups(args.video_id),
        limit=args.limit,
    )
    active_pipeline = pipeline or build_pipeline(args)
    processed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []

    for episode in episodes:
        plot_beats_path = _plot_beats_path(args.plot_beat_root, episode.video_id)
        output_path = _asset_output_path(args.output_root, episode.video_id)
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"SKIP {episode.video_id}: existing {output_path}")
            continue
        if not plot_beats_path.exists():
            failed.append((episode.video_id, f"missing plot beats: {plot_beats_path}"))
            print(f"FAIL {episode.video_id}: missing plot beats {plot_beats_path}")
            continue

        print(f"RUN  {episode.video_id}")
        try:
            result = active_pipeline.run(plot_beats_path=plot_beats_path, subtitle_file_path=episode.subtitle_path)
            written_path = write_from_plot_beats_output(result=result, output_root=args.output_root)
        except Exception as exc:  # noqa: BLE001 - batch jobs should continue and report all episode failures.
            failed.append((episode.video_id, str(exc)))
            diagnostic_path = write_failure_diagnostics(
                episode=episode,
                output_root=args.output_root,
                error=exc,
                metadata={},
                danmaku_items=[],
                llm_call=getattr(active_pipeline, "last_llm_call", {}),
            )
            print(f"FAIL {episode.video_id}: {exc} (diagnostics: {diagnostic_path})")
            continue
        processed += 1
        print(f"WROTE {written_path}")

    print(f"DONE processed={processed} skipped={skipped} failed={len(failed)}")
    if failed:
        for video_id, error in failed:
            print(f"FAILED {video_id}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

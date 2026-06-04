from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.factory import build_ark_client, build_llm_client
from scripts.algorithm.common import (
    DEFAULT_DATA_ROOT,
    EpisodeInput,
    discover_episodes,
    extract_danmaku_items,
    extract_video_metadata,
    load_source_payload,
    now_iso,
    write_failure_diagnostics,
)
from scripts.algorithm_danmaku_csv import load_danmaku_csv_items


DEFAULT_OUTPUT_ROOT = Path("output")


def build_pipeline(
    *,
    env_path: Path,
    sample_interval_sec: float,
    max_frames: int | None,
    enable_danmaku_enhancement: bool,
):
    from pipelines.expression_trigger_detection import ExpressionTriggerPipeline

    return ExpressionTriggerPipeline(
        llm_client=build_llm_client(env_path=env_path),
        sample_interval_sec=sample_interval_sec,
        max_frames=max_frames,
        enable_danmaku_enhancement=enable_danmaku_enhancement,
    )


def write_episode_output(
    *,
    episode: EpisodeInput,
    output_root: Path,
    expression_triggers: list[dict[str, Any]],
    llm_call: dict[str, Any] | None = None,
) -> Path:
    output_dir = output_root / episode.video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": episode.video_id,
        "video_path": str(episode.video_path),
        "source_json_path": str(episode.source_json_path) if episode.source_json_path else None,
        "subtitle_path": str(episode.subtitle_path),
        "created_at": now_iso(),
        "llm_call": llm_call or {},
        "expression_triggers": expression_triggers,
        "highlight_assets": expression_triggers_to_highlight_assets(expression_triggers),
    }
    output_path = output_dir / "highlight_recognition.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def expression_trigger_to_highlight_asset(trigger: dict[str, Any], *, index: int) -> dict[str, Any]:
    video_id = str(trigger["video_id"])
    confidence = float(trigger.get("confidence", 0.0))
    return {
        "highlight_id": f"h_{video_id}_{index:03d}",
        "video_id": video_id,
        "start_time": float(trigger["start_time"]),
        "end_time": float(trigger["end_time"]),
        "highlight_type": str(trigger.get("source_type", "")),
        "emotion": str(trigger.get("primary_expression", "")),
        "intensity": float(trigger.get("intensity", 0.0)),
        "summary": str(trigger.get("summary", "")),
        "setup": str(trigger.get("setup", "")),
        "turning_point": str(trigger.get("turning_point", "")),
        "expression_release": str(trigger.get("expression_release", "")),
        "reason": str(trigger.get("reason", "")),
        "confidence": confidence,
        "highlight_score": confidence,
        "status": str(trigger.get("status") or "verified"),
        "created_at": str(trigger.get("created_at") or now_iso()),
        "updated_at": str(trigger.get("updated_at") or now_iso()),
    }


def expression_triggers_to_highlight_assets(triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [expression_trigger_to_highlight_asset(trigger, index=index) for index, trigger in enumerate(triggers, start=1)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run Expression Trigger Detection over DataForAlgorithm episodes.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--series-id",
        nargs="+",
        action="append",
        help="Only process selected series directories, for example --series-id beiwang nanian_dongzhi.",
    )
    parser.add_argument(
        "--episode-id",
        nargs="+",
        action="append",
        help="Only process selected episode directories across selected series, for example --episode-id ep01 ep02.",
    )
    parser.add_argument(
        "--video-id",
        nargs="+",
        action="append",
        help="Only process exact video ids, for example --video-id beiwang_ep01 nanian_dongzhi_ep02.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Process at most N episodes. Default: all.")
    parser.add_argument("--force", action="store_true", help="Regenerate outputs that already exist.")
    parser.add_argument("--include-finale-trigger", action="store_true")
    parser.add_argument(
        "--disable-danmaku-enhancement",
        action="store_true",
        help="Only use multimodal LLM cold-start detection and skip rule-based danmaku supplemental triggers.",
    )
    parser.add_argument("--sample-interval-sec", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int)
    return parser


def main(argv: Sequence[str] | None = None, *, pipeline: Any | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
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
        sample_interval_sec=args.sample_interval_sec,
        max_frames=args.max_frames,
        enable_danmaku_enhancement=not args.disable_danmaku_enhancement,
    )

    processed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    for episode in episodes:
        output_path = args.output_root / episode.video_id / "highlight_recognition.json"
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"SKIP {episode.video_id}: existing {output_path}")
            continue
        print(f"RUN  {episode.video_id}")
        source_payload = load_source_payload(episode.source_json_path)
        metadata = extract_video_metadata(source_payload)
        danmaku_items: list[dict[str, Any]] = []
        llm_call: dict[str, Any] = {}
        try:
            danmaku_items = load_danmaku_csv_items(args.data_root, series_id=episode.series_id, episode_id=episode.episode_id)
            if not danmaku_items:
                danmaku_items = extract_danmaku_items(source_payload)
            expression_triggers = active_pipeline.run(
                video_id=episode.video_id,
                video_file_path=episode.video_path,
                subtitle_file_path=episode.subtitle_path,
                metadata=metadata,
                danmaku_items=danmaku_items,
                include_finale_trigger=args.include_finale_trigger,
            )
            raw_llm_call = getattr(active_pipeline, "last_llm_call", {})
            llm_call = dict(raw_llm_call) if isinstance(raw_llm_call, dict) else {}
            written_path = write_episode_output(
                episode=episode,
                output_root=args.output_root,
                expression_triggers=expression_triggers,
                llm_call=llm_call,
            )
        except Exception as exc:  # noqa: BLE001 - batch jobs should continue and report all episode failures.
            raw_llm_call = getattr(active_pipeline, "last_llm_call", {})
            llm_call = dict(raw_llm_call) if isinstance(raw_llm_call, dict) else llm_call
            failed.append((episode.video_id, str(exc)))
            diagnostic_path = write_failure_diagnostics(
                episode=episode,
                output_root=args.output_root,
                error=exc,
                metadata=metadata,
                danmaku_items=danmaku_items,
                llm_call=llm_call,
            )
            print(f"FAIL {episode.video_id}: {exc} (diagnostics: {diagnostic_path})", file=sys.stderr)
            continue
        processed += 1
        print(f"WROTE {written_path}")

    print(f"Done. discovered={len(episodes)} processed={processed} skipped={skipped} failed={len(failed)}")
    if failed:
        for video_id, error in failed:
            print(f"- {video_id}: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

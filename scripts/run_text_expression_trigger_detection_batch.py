from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_expression_trigger_detection_batch import (
    DEFAULT_DATA_ROOT,
    discover_episodes,
    extract_video_metadata,
    load_source_payload,
    build_llm_client,
    write_episode_output,
    write_failure_diagnostics,
)


DEFAULT_OUTPUT_ROOT = Path("output/text_expression_trigger")


def build_pipeline(*, env_path: Path, max_output_tokens: int):
    from pipelines.text_expression_trigger_detection import TextExpressionTriggerPipeline

    return TextExpressionTriggerPipeline(
        llm_client=build_llm_client(env_path=env_path),
        max_output_tokens=max_output_tokens,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run subtitle-only Expression Trigger Detection over DataForAlgorithm episodes.")
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
    parser.add_argument("--max-output-tokens", type=int, default=2400)
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
        max_output_tokens=args.max_output_tokens,
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
        llm_call: dict[str, Any] = {}
        try:
            expression_triggers = active_pipeline.run(
                video_id=episode.video_id,
                subtitle_file_path=episode.subtitle_path,
                metadata=metadata,
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
                danmaku_items=[],
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

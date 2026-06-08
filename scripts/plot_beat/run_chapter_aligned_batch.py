from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.client.factory import build_llm_client
from pipelines.plot_beat.chapter_aligned import ChapterAlignedPlotBeatPipeline
from scripts.algorithm.common import DEFAULT_DATA_ROOT, discover_episodes


DEFAULT_STORY_CHAPTER_ROOT = Path("output/story_chapter")
DEFAULT_OUTPUT_ROOT = Path("output/plot_beat/chapter_aligned")
OUTPUT_FILENAME = "plot_beats.json"
DEBUG_FILENAME = "plot_beats.debug.json"


def _format_optional_number(value: Any, *, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def print_plot_beat_progress(event: str, payload: dict[str, Any]) -> None:
    video_id = str(payload.get("video_id") or "unknown")
    if event == "prepared":
        print(
            f"[{video_id}] prepared: "
            f"chapters={payload.get('chapter_count', 0)} "
            f"subtitles={payload.get('subtitle_segment_count', 0)} "
            f"duration={_format_optional_number(payload.get('duration_sec'), suffix='s')}"
        )
        return
    if event == "chapter_start":
        print(
            f"[{video_id}] chapter_start "
            f"[{payload.get('chapter_index', '?')}/{payload.get('chapter_count', '?')}] "
            f"{payload.get('chapter_id')} "
            f"{payload.get('start_time')}-{payload.get('end_time')}s "
            f"title={payload.get('title')}"
        )
        return
    if event == "chapter_frames_extracted":
        print(
            f"[{video_id}] chapter_frames_extracted {payload.get('chapter_id')}: "
            f"requested={payload.get('requested_frame_count', 0)} "
            f"extracted={payload.get('extracted_frame_count', 0)} "
            f"images={payload.get('image_count', 0)}"
        )
        return
    if event == "chapter_llm_start":
        print(
            f"[{video_id}] chapter_llm_start {payload.get('chapter_id')}: "
            f"frames={payload.get('frame_count', 0)} "
            f"images={payload.get('image_count', 0)} "
            f"max_tokens={payload.get('max_tokens')}"
        )
        return
    if event == "chapter_llm_done":
        print(
            f"[{video_id}] chapter_llm_done {payload.get('chapter_id')}: "
            f"beats={payload.get('beat_count', 0)} "
            f"elapsed={_format_optional_number(payload.get('elapsed_sec'), suffix='s')} "
            f"tokens={_format_optional_number(payload.get('total_tokens'))}"
        )
        return
    if event == "completed":
        print(
            f"[{video_id}] completed: "
            f"chapters={payload.get('chapter_count', 0)} "
            f"beats={payload.get('beat_count', 0)}"
        )
        return
    print(f"[{video_id}] {event}: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run chapter-aligned Plot Beat detection.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--story-chapter-root", type=Path, default=DEFAULT_STORY_CHAPTER_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--series-id", nargs="+", action="append", help="Only process selected series ids.")
    parser.add_argument("--episode-id", nargs="+", action="append", help="Only process selected episode ids such as ep01.")
    parser.add_argument("--video-id", nargs="+", action="append", help="Only process exact video ids such as beiwang_ep01.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="Regenerate outputs that already exist.")
    parser.add_argument("--frame-interval-sec", type=float, default=1.0)
    parser.add_argument("--max-chapter-frames", type=int, default=60)
    parser.add_argument("--frame-max-height", type=int, default=512)
    parser.add_argument("--max-output-tokens", type=int, default=2400)
    return parser


def _flatten_groups(groups: list[list[str]] | None) -> list[str]:
    return [item for group in (groups or []) for item in group]


def _story_chapters_path(story_chapter_root: Path, video_id: str) -> Path:
    return story_chapter_root / video_id / "story_chapters.json"


def _output_path(output_root: Path, video_id: str) -> Path:
    return output_root / video_id / OUTPUT_FILENAME


def _debug_output_path(output_root: Path, video_id: str) -> Path:
    return output_root / video_id / DEBUG_FILENAME


def write_plot_beat_output(*, result: Any, output_root: Path) -> Path:
    output_path = _output_path(output_root, str(result.video_id))
    debug_path = _debug_output_path(output_root, str(result.video_id))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": result.video_id,
        "series_id": result.series_id,
        "created_at": result.created_at,
        "chapter_plot_beats": result.chapter_plot_beats,
    }
    debug_payload = {
        "video_id": result.video_id,
        "series_id": result.series_id,
        "created_at": result.created_at,
        "llm_calls": result.llm_calls,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_pipeline(args: argparse.Namespace) -> ChapterAlignedPlotBeatPipeline:
    return ChapterAlignedPlotBeatPipeline(
        llm_client=build_llm_client(env_path=args.env_file),
        frame_interval_sec=args.frame_interval_sec,
        max_chapter_frames=args.max_chapter_frames,
        frame_max_height=args.frame_max_height,
        max_output_tokens=args.max_output_tokens,
        progress_callback=print_plot_beat_progress,
    )


def main(argv: Sequence[str] | None = None, *, pipeline: Any | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    series_ids = _flatten_groups(args.series_id)
    episode_ids = _flatten_groups(args.episode_id)
    video_ids = _flatten_groups(args.video_id)
    episodes = discover_episodes(
        data_root=args.data_root,
        series_ids=series_ids,
        episode_ids=episode_ids,
        video_ids=video_ids,
        limit=args.limit,
    )
    active_pipeline = pipeline or build_pipeline(args)
    failed: list[tuple[str, str]] = []
    processed = 0
    skipped = 0

    for episode in episodes:
        story_chapters_path = _story_chapters_path(args.story_chapter_root, episode.video_id)
        output_path = _output_path(args.output_root, episode.video_id)
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"SKIP {episode.video_id}: existing {output_path}")
            continue
        if not story_chapters_path.exists():
            failed.append((episode.video_id, f"missing story chapters: {story_chapters_path}"))
            print(f"FAIL {episode.video_id}: missing story chapters {story_chapters_path}")
            continue

        print(f"RUN  {episode.video_id}")
        try:
            result = active_pipeline.run(
                video_file_path=episode.video_path,
                subtitle_file_path=episode.subtitle_path,
                story_chapters_path=story_chapters_path,
            )
            written_path = write_plot_beat_output(result=result, output_root=args.output_root)
        except Exception as exc:  # noqa: BLE001 - batch should continue and report all failures.
            failed.append((episode.video_id, str(exc)))
            print(f"FAIL {episode.video_id}: {exc}")
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

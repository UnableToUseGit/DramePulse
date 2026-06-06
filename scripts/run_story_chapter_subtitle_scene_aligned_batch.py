from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.story_chapter.subtitle_scene_aligned import StoryChapterSubtitleSceneAlignedPipeline
from scripts.run_story_chapter_generation import load_video_metadata_from_scene_detection
from scripts.run_story_chapter_generation_batch import DEFAULT_DATASET_ROOT
from scripts.run_story_chapter_subtitle_scene_aligned import build_pipeline
from scripts.run_story_chapter_workflow_batch import discover_workflow_inputs


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run subtitle-first, scene-aligned story chapter workflow.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-root", type=Path, default=Path("output/story_chapter_subtitle_scene_aligned_validation"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--series-id", action="append", default=[])
    parser.add_argument("--episode-id", action="append", default=[])
    parser.add_argument("--max-alignment-window-seconds", type=float, default=10.0)
    parser.add_argument("--min-chapter-seconds", type=float, default=12.0)
    return parser


def _summary_path(output_root: Path) -> Path:
    return output_root / "story_chapter_subtitle_scene_aligned_batch_summary.json"


def _output_path_for(output_root: Path, video_id: str) -> Path:
    return output_root / video_id / "story_chapters.json"


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: StoryChapterSubtitleSceneAlignedPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    inputs = discover_workflow_inputs(args.dataset_root, series_ids=args.series_id, episode_ids=args.episode_id)
    if args.limit is not None:
        inputs = inputs[: args.limit]
    args.output_root.mkdir(parents=True, exist_ok=True)
    active_pipeline = pipeline or build_pipeline(args)
    print(
        f"Discovered {len(inputs)} subtitle-scene aligned inputs "
        f"series={args.series_id or 'ALL'} episodes={args.episode_id or 'ALL'} output_root={args.output_root}",
        flush=True,
    )

    results: list[dict[str, object]] = []
    succeeded = 0
    failed = 0
    skipped = 0
    for index, item in enumerate(inputs, start=1):
        output_path = _output_path_for(args.output_root, item.video_id)
        if args.only_missing and output_path.exists():
            skipped += 1
            print(f"[{index}/{len(inputs)}] skip existing {item.video_id}", flush=True)
            results.append({"video_id": item.video_id, "status": "skipped", "output_path": str(output_path), "error": None})
            continue
        print(f"[{index}/{len(inputs)}] run subtitle-scene aligned {item.video_id}", flush=True)
        try:
            written_path = active_pipeline.run(
                video_id=item.video_id,
                video_path=item.video_path,
                video_metadata=load_video_metadata_from_scene_detection(item.scene_detection_path),
                transcription_path=item.transcription_path,
                scene_detection_path=item.scene_detection_path,
                output_root=args.output_root,
            )
        except Exception as exc:  # noqa: BLE001 - batch should continue and report per-episode failures.
            failed += 1
            print(f"[{index}/{len(inputs)}] failed {item.video_id}: {exc}", flush=True)
            results.append({"video_id": item.video_id, "status": "failed", "output_path": str(output_path), "error": str(exc)})
            continue
        succeeded += 1
        print(f"[{index}/{len(inputs)}] succeeded {item.video_id}: {written_path}", flush=True)
        results.append({"video_id": item.video_id, "status": "succeeded", "output_path": str(written_path), "error": None})

    summary = {
        "created_at": _now_iso(),
        "dataset_root": str(args.dataset_root),
        "output_root": str(args.output_root),
        "total": len(inputs),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }
    summary_path = _summary_path(args.output_root)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote subtitle-scene aligned batch summary: {summary_path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.story_chapter_generation import StoryChapterPipeline
from scripts.story_chapter.run_text import build_ark_client, load_video_metadata_from_scene_detection


DEFAULT_DATASET_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")


@dataclass(frozen=True)
class StoryChapterInput:
    video_id: str
    series_slug: str
    episode_slug: str
    transcription_path: Path
    scene_detection_path: Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_video_id(scene_detection_path: Path, fallback: str) -> str:
    try:
        payload = json.loads(scene_detection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    video_id = str(payload.get("video_id") or "").strip()
    return video_id or fallback


def discover_story_chapter_inputs(dataset_root: Path) -> list[StoryChapterInput]:
    if not dataset_root.exists():
        raise FileNotFoundError(dataset_root)

    inputs: list[StoryChapterInput] = []
    series_dirs = sorted(path for path in dataset_root.iterdir() if path.is_dir() and not path.name.startswith("."))
    for series_dir in series_dirs:
        episode_dirs = sorted(path for path in series_dir.iterdir() if path.is_dir() and not path.name.startswith("."))
        for episode_dir in episode_dirs:
            transcription_path = episode_dir / "video.transcription.json"
            scene_detection_path = episode_dir / "scene_detection.json"
            if not transcription_path.exists() or not scene_detection_path.exists():
                continue
            fallback_video_id = f"{series_dir.name}_{episode_dir.name}"
            inputs.append(
                StoryChapterInput(
                    video_id=_safe_video_id(scene_detection_path, fallback_video_id),
                    series_slug=series_dir.name,
                    episode_slug=episode_dir.name,
                    transcription_path=transcription_path,
                    scene_detection_path=scene_detection_path,
                )
            )
    return inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run story chapter generation for a dataset root.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-root", type=Path, default=Path("output/story_chapter_validation"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to dotenv file. Defaults to .env.")
    parser.add_argument("--limit", type=int, help="Run at most N discovered episodes.")
    parser.add_argument("--only-missing", action="store_true", help="Skip episodes with existing story_chapters.json.")
    return parser


def _summary_path(output_root: Path) -> Path:
    return output_root / "story_chapter_generation_batch_summary.json"


def _output_path_for(output_root: Path, video_id: str) -> Path:
    return output_root / video_id / "story_chapters.json"


def _input_result_fields(item: StoryChapterInput) -> dict[str, object]:
    return {
        "video_id": item.video_id,
        "series_slug": item.series_slug,
        "episode_slug": item.episode_slug,
        "transcription_path": str(item.transcription_path),
        "scene_detection_path": str(item.scene_detection_path),
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: StoryChapterPipeline | None = None,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    inputs = discover_story_chapter_inputs(args.dataset_root)
    if args.limit is not None:
        inputs = inputs[: args.limit]

    args.output_root.mkdir(parents=True, exist_ok=True)
    active_pipeline = pipeline or StoryChapterPipeline(llm_client=build_ark_client(env_path=args.env_file))

    results: list[dict[str, object]] = []
    succeeded = 0
    failed = 0
    skipped = 0

    for index, item in enumerate(inputs, start=1):
        output_path = _output_path_for(args.output_root, item.video_id)
        if args.only_missing and output_path.exists():
            skipped += 1
            print(f"[{index}/{len(inputs)}] skip existing {item.video_id}")
            results.append(
                {
                    **_input_result_fields(item),
                    "status": "skipped",
                    "output_path": str(output_path),
                    "error": None,
                }
            )
            continue

        print(f"[{index}/{len(inputs)}] run {item.video_id}")
        try:
            written_path = active_pipeline.run(
                video_id=item.video_id,
                video_metadata=load_video_metadata_from_scene_detection(item.scene_detection_path),
                transcription_path=item.transcription_path,
                scene_detection_path=item.scene_detection_path,
                output_root=args.output_root,
            )
        except Exception as exc:  # noqa: BLE001 - batch should continue and report per-episode failures.
            failed += 1
            print(f"[{index}/{len(inputs)}] failed {item.video_id}: {exc}")
            results.append(
                {
                    **_input_result_fields(item),
                    "status": "failed",
                    "output_path": str(output_path),
                    "error": str(exc),
                }
            )
            continue

        succeeded += 1
        results.append(
            {
                **_input_result_fields(item),
                "status": "succeeded",
                "output_path": str(written_path),
                "error": None,
            }
        )

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
    path = _summary_path(args.output_root)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote batch summary: {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

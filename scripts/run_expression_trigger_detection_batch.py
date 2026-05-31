from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.algorithm_danmaku_csv import load_danmaku_csv_items
from scripts.transcription.env import load_dotenv_values


DEFAULT_DATA_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")
DEFAULT_OUTPUT_ROOT = Path("output")


@dataclass(frozen=True)
class EpisodeInput:
    video_id: str
    series_id: str
    episode_id: str
    episode_dir: Path
    video_path: Path
    subtitle_path: Path
    source_json_path: Path | None


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def discover_episodes(
    *,
    data_root: Path,
    series_id: str | None = None,
    episode_id: str | None = None,
    limit: int = 0,
) -> list[EpisodeInput]:
    episodes: list[EpisodeInput] = []
    for video_path in sorted(data_root.glob("*/ep*/video.mp4")):
        current_episode_dir = video_path.parent
        current_series_id = current_episode_dir.parent.name
        current_episode_id = current_episode_dir.name
        if series_id and current_series_id != series_id:
            continue
        if episode_id and current_episode_id != episode_id:
            continue
        subtitle_path = current_episode_dir / "video.srt"
        if not subtitle_path.exists():
            continue
        source_json_path = current_episode_dir / "douyin.json"
        episodes.append(
            EpisodeInput(
                video_id=f"{current_series_id}_{current_episode_id}",
                series_id=current_series_id,
                episode_id=current_episode_id,
                episode_dir=current_episode_dir,
                video_path=video_path,
                subtitle_path=subtitle_path,
                source_json_path=source_json_path if source_json_path.exists() else None,
            )
        )
        if limit > 0 and len(episodes) >= limit:
            break
    return episodes


def load_source_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def extract_video_metadata(source_payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    raw_metadata = source_payload.get("metadata")
    if isinstance(raw_metadata, dict):
        for key in ("title", "description", "duration_ms"):
            if key in raw_metadata:
                metadata[key] = raw_metadata[key]
        series = raw_metadata.get("series")
        if isinstance(series, dict):
            if "name" in series:
                metadata["series_name"] = series["name"]
            if "current_episode" in series:
                metadata["episode_no"] = series["current_episode"]
            if "total_episode" in series:
                metadata["total_episode"] = series["total_episode"]
    for key in ("title", "description", "series_name", "episode_label", "episode_no", "source_url", "duration_ms"):
        if key in source_payload:
            metadata[key] = source_payload[key]
    if source_payload.get("video_url"):
        metadata["source_url"] = source_payload["video_url"]
    return metadata


def _normalize_danmaku_item(item: dict[str, Any]) -> dict[str, Any] | None:
    text = str(item.get("text") or item.get("content") or "").strip()
    if not text:
        return None
    try:
        if item.get("time_sec") is not None:
            time_sec = float(item["time_sec"])
        elif item.get("time_ms") is not None:
            time_sec = float(item["time_ms"]) / 1000.0
        else:
            return None
    except (TypeError, ValueError):
        return None
    normalized = dict(item)
    normalized["time_sec"] = round(time_sec, 3)
    normalized["text"] = text
    return normalized


def extract_danmaku_items(source_payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = (
        source_payload.get("danmaku"),
        source_payload.get("items"),
        source_payload.get("comments"),
    )
    raw_items: Any = []
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("items"), list):
            raw_items = candidate["items"]
            break
        if isinstance(candidate, list):
            raw_items = candidate
            break
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item = _normalize_danmaku_item(raw_item)
        if item is not None:
            items.append(item)
    return items


def build_ark_client(*, env_path: Path | None = None):
    from pipelines.client import VolcArkLlmClient

    dotenv_values = load_dotenv_values(env_path)
    return VolcArkLlmClient(
        api_key=dotenv_values.get("ARK_API_KEY") or os.environ.get("ARK_API_KEY") or None,
        base_url=dotenv_values.get("ARK_BASE_URL") or os.environ.get("ARK_BASE_URL") or None,
        model_name=dotenv_values.get("ARK_MODEL") or os.environ.get("ARK_MODEL") or None,
    )


def build_pipeline(*, env_path: Path, sample_interval_sec: float, frames_per_interval: int, max_frames: int | None):
    from pipelines.expression_trigger_detection import ExpressionTriggerPipeline

    return ExpressionTriggerPipeline(
        llm_client=build_ark_client(env_path=env_path),
        sample_interval_sec=sample_interval_sec,
        frames_per_interval=frames_per_interval,
        max_frames=max_frames,
    )


def write_episode_output(
    *,
    episode: EpisodeInput,
    output_root: Path,
    expression_triggers: list[dict[str, Any]],
) -> Path:
    output_dir = output_root / episode.video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": episode.video_id,
        "video_path": str(episode.video_path),
        "source_json_path": str(episode.source_json_path) if episode.source_json_path else None,
        "subtitle_path": str(episode.subtitle_path),
        "created_at": now_iso(),
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
    parser.add_argument("--series-id", help="Only process one series directory, for example beipai_xunbao_biji.")
    parser.add_argument("--episode-id", help="Only process one episode directory, for example ep01.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N episodes. Default: all.")
    parser.add_argument("--force", action="store_true", help="Regenerate outputs that already exist.")
    parser.add_argument("--include-finale-trigger", action="store_true")
    parser.add_argument("--sample-interval-sec", type=float, default=1.0)
    parser.add_argument("--frames-per-interval", type=int, default=1)
    parser.add_argument("--max-frames", type=int)
    return parser


def main(argv: Sequence[str] | None = None, *, pipeline: Any | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    episodes = discover_episodes(
        data_root=args.data_root,
        series_id=args.series_id,
        episode_id=args.episode_id,
        limit=args.limit,
    )
    active_pipeline = pipeline or build_pipeline(
        env_path=args.env_file,
        sample_interval_sec=args.sample_interval_sec,
        frames_per_interval=args.frames_per_interval,
        max_frames=args.max_frames,
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
        try:
            danmaku_items = load_danmaku_csv_items(args.data_root, series_id=episode.series_id, episode_id=episode.episode_id)
            if not danmaku_items:
                danmaku_items = extract_danmaku_items(source_payload)
            expression_triggers = active_pipeline.run(
                video_id=episode.video_id,
                video_file_path=episode.video_path,
                subtitle_file_path=episode.subtitle_path,
                metadata=extract_video_metadata(source_payload),
                danmaku_items=danmaku_items,
                include_finale_trigger=args.include_finale_trigger,
            )
            written_path = write_episode_output(
                episode=episode,
                output_root=args.output_root,
                expression_triggers=expression_triggers,
            )
        except Exception as exc:  # noqa: BLE001 - batch jobs should continue and report all episode failures.
            failed.append((episode.video_id, str(exc)))
            print(f"FAIL {episode.video_id}: {exc}", file=sys.stderr)
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

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Sequence


DEFAULT_DATA_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")


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
    series_ids: Sequence[str] | None = None,
    episode_id: str | None = None,
    episode_ids: Sequence[str] | None = None,
    video_ids: Sequence[str] | None = None,
    limit: int = 0,
) -> list[EpisodeInput]:
    allowed_series_ids = set(series_ids or [])
    if series_id:
        allowed_series_ids.add(series_id)
    allowed_episode_ids = set(episode_ids or [])
    if episode_id:
        allowed_episode_ids.add(episode_id)
    allowed_video_ids = set(video_ids or [])
    episodes: list[EpisodeInput] = []
    for video_path in sorted(data_root.glob("*/ep*/video.mp4")):
        current_episode_dir = video_path.parent
        current_series_id = current_episode_dir.parent.name
        current_episode_id = current_episode_dir.name
        current_video_id = f"{current_series_id}_{current_episode_id}"
        if allowed_series_ids and current_series_id not in allowed_series_ids:
            continue
        if allowed_episode_ids and current_episode_id not in allowed_episode_ids:
            continue
        if allowed_video_ids and current_video_id not in allowed_video_ids:
            continue
        subtitle_path = current_episode_dir / "video.srt"
        if not subtitle_path.exists():
            continue
        source_json_path = current_episode_dir / "douyin.json"
        episodes.append(
            EpisodeInput(
                video_id=current_video_id,
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


def write_failure_diagnostics(
    *,
    episode: EpisodeInput,
    output_root: Path,
    error: Exception,
    metadata: dict[str, Any],
    danmaku_items: list[dict[str, Any]],
    llm_call: dict[str, Any] | None = None,
) -> Path:
    output_dir = output_root / episode.video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_response_text = getattr(error, "raw_response_text", "")
    payload = {
        "video_id": episode.video_id,
        "series_id": episode.series_id,
        "episode_id": episode.episode_id,
        "video_path": str(episode.video_path),
        "source_json_path": str(episode.source_json_path) if episode.source_json_path else None,
        "subtitle_path": str(episode.subtitle_path),
        "created_at": now_iso(),
        "error_type": type(error).__name__,
        "error": str(error),
        "metadata": metadata,
        "danmaku_count": len(danmaku_items),
        "llm_call": llm_call or {},
        "raw_response_text": raw_response_text if isinstance(raw_response_text, str) else str(raw_response_text),
    }
    output_path = output_dir / "llm_failure.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "DEFAULT_DATA_ROOT",
    "EpisodeInput",
    "discover_episodes",
    "extract_danmaku_items",
    "extract_video_metadata",
    "load_source_payload",
    "now_iso",
    "write_failure_diagnostics",
]

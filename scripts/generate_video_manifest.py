from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path as _Path
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))


from scripts.douyin_danmaku_collector import SERIES_SLUGS


SCHEMA_VERSION = "video_manifest.v1"
DEFAULT_BUCKET = "local"
DEFAULT_CONTENT_TYPE = "video/mp4"


def _series_names_by_id() -> dict[str, str]:
    return {series_id: series_name for series_name, series_id in SERIES_SLUGS.items()}


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _episode_no_from_label(label: str) -> int:
    match = re.fullmatch(r"ep(\d+)", label)
    if not match:
        raise ValueError(f"episode directory must use epXX format, got: {label}")
    number = int(match.group(1))
    if number <= 0:
        raise ValueError(f"episode number must be positive, got: {label}")
    return number


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def _duration_seconds(douyin_data: dict[str, Any]) -> float | None:
    metadata = douyin_data.get("metadata") or {}
    duration_ms = metadata.get("duration_ms")
    if duration_ms is None:
        return None
    return round(float(duration_ms) / 1000, 3)


def _danmaku_count(douyin_data: dict[str, Any]) -> int:
    danmaku = douyin_data.get("danmaku") or {}
    count = danmaku.get("count")
    if count is not None:
        return int(count)
    items = danmaku.get("items") or []
    return len(items)


def build_video_entry(data_root: Path, episode_dir: Path) -> dict[str, Any]:
    data_root = data_root.resolve()
    episode_dir = episode_dir.resolve()
    video_path = episode_dir / "video.mp4"
    douyin_path = episode_dir / "douyin.json"
    if not video_path.is_file():
        raise FileNotFoundError(f"Missing video.mp4: {video_path}")

    raw_dir = data_root / "raw"
    series_id = episode_dir.parent.name
    episode_label = episode_dir.name
    series_names = _series_names_by_id()
    if series_id not in series_names:
        raise ValueError(f"Unknown series_id: {series_id}")

    episode_no = _episode_no_from_label(episode_label)
    douyin_available = douyin_path.is_file()
    douyin_data = _load_json(douyin_path) if douyin_available else {}
    metadata = douyin_data.get("metadata") or {}
    title = metadata.get("title") or f"{series_names[series_id]} {episode_label}"
    douyin_video_id = str(douyin_data.get("video_id") or douyin_data.get("episode_id") or "").strip() or None
    if douyin_available and not douyin_video_id:
        raise ValueError(f"Missing douyin video_id: {douyin_path}")
    douyin_video_url = (
        str(douyin_data.get("video_url") or f"https://www.douyin.com/video/{douyin_video_id}")
        if douyin_video_id
        else None
    )

    return {
        "video_id": f"{series_id}_{episode_label}",
        "series_id": series_id,
        "series_name": series_names[series_id],
        "episode_no": episode_no,
        "episode_label": episode_label,
        "title": str(title),
        "duration": _duration_seconds(douyin_data),
        "source": "local",
        "status": "active",
        "storage": {
            "bucket": DEFAULT_BUCKET,
            "object_key": _relative_posix(video_path, data_root),
            "content_type": DEFAULT_CONTENT_TYPE,
            "size": video_path.stat().st_size,
        },
        "douyin": {
            "video_id": douyin_video_id,
            "video_url": douyin_video_url,
            "json_path": _relative_posix(douyin_path, data_root) if douyin_available else None,
            "danmaku_count": _danmaku_count(douyin_data) if douyin_available else 0,
            "available": douyin_available,
        },
    }


def _episode_dirs(data_root: Path) -> list[Path]:
    raw_dir = data_root / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Missing raw directory: {raw_dir}")
    return sorted(path for path in raw_dir.glob("*/ep*") if path.is_dir())


def generate_manifest(data_root: Path) -> dict[str, Any]:
    resolved_root = data_root.resolve()
    videos = [build_video_entry(resolved_root, episode_dir) for episode_dir in _episode_dirs(resolved_root)]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "videos": videos,
    }


def write_manifest(data_root: Path, output: Path | None = None) -> Path:
    manifest = generate_manifest(data_root)
    output_path = output or data_root / "video_manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate video_manifest.json from VideoData/raw.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    output_path = write_manifest(args.data_root, args.output)
    print(f"Generated video manifest: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

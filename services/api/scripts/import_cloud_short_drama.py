from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.api.config import get_settings, require_complete_cloud_settings
from services.api.db import db_cursor
from services.api.oss_client import get_bucket


DEFAULT_SOURCE_ROOT = Path(r"D:\XuPlace\bytedance\project\Vedio\shibasui_tainainai\shibasui_tainainai")
DEFAULT_SERIES_ID = "shibasui_tainainai"
DEFAULT_OBJECT_PREFIX = "raw/shibasui_tainainai"
DEFAULT_CONTENT_TYPE = "video/mp4"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def _episode_no(label: str) -> int:
    if not label.startswith("ep"):
        raise ValueError(f"episode directory must use epXX format: {label}")
    number = int(label[2:])
    if number <= 0:
        raise ValueError(f"episode number must be positive: {label}")
    return number


def _safe_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _duration_seconds(douyin_data: dict[str, Any]) -> float | None:
    duration_ms = (douyin_data.get("metadata") or {}).get("duration_ms")
    if duration_ms is None:
        return None
    return round(float(duration_ms) / 1000, 3)


def _series_name(douyin_data: dict[str, Any], fallback: str) -> str:
    metadata = douyin_data.get("metadata") or {}
    series = metadata.get("series") or {}
    return _safe_text(series.get("name"), fallback)


def _title(douyin_data: dict[str, Any], fallback: str) -> str:
    return _safe_text((douyin_data.get("metadata") or {}).get("title"), fallback)


def _danmaku_id(video_id: str, item: dict[str, Any], index: int) -> str:
    raw_id = str(item.get("danmaku_id") or item.get("id") or item.get("cid") or index).strip()
    return f"douyin_{video_id}_{raw_id}"[:64]


def _danmaku_row(video_id: str, item: dict[str, Any], index: int) -> tuple[Any, ...]:
    client_time = float(item.get("time_sec") or 0)
    time_ms = int(item.get("time_ms") or round(client_time * 1000))
    return (
        _danmaku_id(video_id, item, index),
        video_id,
        item.get("user_id"),
        client_time,
        time_ms,
        str(item.get("text") or "").strip(),
        "douyin",
        int(item.get("digg_count") or 0),
        float(item.get("score") or 0),
        "active",
        json.dumps(item, ensure_ascii=False),
    )


def _episode_dirs(source_root: Path) -> list[Path]:
    if not source_root.is_dir():
        raise FileNotFoundError(f"Missing source root: {source_root}")
    return sorted(path for path in source_root.glob("ep*") if path.is_dir())


def _upload_video(bucket: Any, video_path: Path, object_key: str) -> int:
    bucket.put_object_from_file(object_key, str(video_path), headers={"Content-Type": DEFAULT_CONTENT_TYPE})
    meta = bucket.head_object(object_key)
    remote_size = int(meta.headers.get("Content-Length", "0"))
    local_size = video_path.stat().st_size
    if remote_size != local_size:
        raise RuntimeError(f"OSS size mismatch for {object_key}: local={local_size}, remote={remote_size}")
    return remote_size


def _upsert_video(row: tuple[Any, ...]) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO videos (
                video_id, series_id, series_name, title, episode_no, episode_label,
                duration, oss_bucket, oss_object_key, douyin_video_id, douyin_json_path,
                content_type, size, source, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                series_id = VALUES(series_id),
                series_name = VALUES(series_name),
                title = VALUES(title),
                episode_no = VALUES(episode_no),
                episode_label = VALUES(episode_label),
                duration = VALUES(duration),
                oss_bucket = VALUES(oss_bucket),
                oss_object_key = VALUES(oss_object_key),
                douyin_video_id = VALUES(douyin_video_id),
                douyin_json_path = VALUES(douyin_json_path),
                content_type = VALUES(content_type),
                size = VALUES(size),
                source = VALUES(source),
                status = VALUES(status),
                updated_at = UTC_TIMESTAMP(6)
            """,
            row,
        )


def _upsert_danmaku(rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    with db_cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO danmaku_items (
                danmaku_id, video_id, user_id, client_time, time_ms, text,
                source, digg_count, score, status, raw_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                user_id = VALUES(user_id),
                client_time = VALUES(client_time),
                time_ms = VALUES(time_ms),
                text = VALUES(text),
                source = VALUES(source),
                digg_count = VALUES(digg_count),
                score = VALUES(score),
                status = VALUES(status),
                raw_json = VALUES(raw_json)
            """,
            rows,
        )


def import_cloud_short_drama(
    source_root: Path = DEFAULT_SOURCE_ROOT,
    *,
    series_id: str = DEFAULT_SERIES_ID,
    object_prefix: str = DEFAULT_OBJECT_PREFIX,
) -> dict[str, int]:
    settings = get_settings()
    if settings.mode != "cloud":
        raise RuntimeError("DRAMEPULSE_MODE must be cloud")
    require_complete_cloud_settings(settings)

    bucket = get_bucket(settings)
    imported_videos = 0
    imported_danmaku = 0
    for episode_dir in _episode_dirs(source_root):
        episode_label = episode_dir.name
        episode_no = _episode_no(episode_label)
        video_id = f"{series_id}_{episode_label}"
        video_path = episode_dir / "video.mp4"
        douyin_path = episode_dir / "douyin.json"
        if not video_path.is_file():
            raise FileNotFoundError(f"Missing video.mp4: {video_path}")
        if not douyin_path.is_file():
            raise FileNotFoundError(f"Missing douyin.json: {douyin_path}")

        douyin_data = _load_json(douyin_path)
        object_key = f"{object_prefix}/{episode_label}/video.mp4"
        size = _upload_video(bucket, video_path, object_key)
        fallback_title = f"{series_id} {episode_label}"
        _upsert_video(
            (
                video_id,
                series_id,
                _series_name(douyin_data, series_id),
                _title(douyin_data, fallback_title),
                episode_no,
                episode_label,
                _duration_seconds(douyin_data),
                settings.oss_bucket,
                object_key,
                douyin_data.get("video_id") or douyin_data.get("episode_id"),
                f"{object_prefix}/{episode_label}/douyin.json",
                DEFAULT_CONTENT_TYPE,
                size,
                "oss",
                "active",
            )
        )
        imported_videos += 1

        raw_items = (douyin_data.get("danmaku") or {}).get("items") or []
        rows = [
            _danmaku_row(video_id, item, index)
            for index, item in enumerate(raw_items, start=1)
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
        _upsert_danmaku(rows)
        imported_danmaku += len(rows)

    return {"videos": imported_videos, "danmaku_items": imported_danmaku}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload shibasui_tainainai videos to OSS and import metadata/danmaku into MySQL.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--series-id", default=DEFAULT_SERIES_ID)
    parser.add_argument("--object-prefix", default=DEFAULT_OBJECT_PREFIX)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    result = import_cloud_short_drama(
        args.source_root,
        series_id=args.series_id,
        object_prefix=args.object_prefix.strip("/"),
    )
    print(f"Imported {result['videos']} videos and {result['danmaku_items']} danmaku items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

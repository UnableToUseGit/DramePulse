from __future__ import annotations

import argparse
from hashlib import sha1
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.api.config import get_settings, require_complete_cloud_settings
from services.api.db import db_cursor, sql_placeholder
from services.api.oss_client import get_bucket, get_object_meta


DEFAULT_SOURCE_SERIES_ID = "shibasui_tainainai"
DEFAULT_TARGET_SERIES_ID = "tainainai"
DEFAULT_TARGET_OBJECT_PREFIX = "dramas/tainainai"
DEFAULT_TARGET_SERIES_NAME_SUFFIX = "（弹幕存储实验）"
DEFAULT_CONTENT_TYPE = "video/mp4"


def _episode_video_key(object_prefix: str, episode_label: str) -> str:
    return f"{object_prefix}/episodes/{episode_label}/video.mp4"


def _episode_danmaku_key(object_prefix: str, episode_label: str) -> str:
    return f"{object_prefix}/episodes/{episode_label}/danmaku/douyin.json"


def _target_video_id(series_id: str, episode_label: str) -> str:
    return f"{series_id}_{episode_label}"


def _target_danmaku_id(target_video_id: str, source_danmaku_id: str) -> str:
    digest = sha1(source_danmaku_id.encode("utf-8")).hexdigest()[:16]
    return f"copy_{target_video_id}_{digest}"[:64]


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _get_source_videos(source_series_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                video_id,
                series_id,
                series_name,
                title,
                episode_no,
                episode_label,
                duration,
                douyin_video_id,
                content_type,
                status
            FROM videos
            WHERE series_id = {placeholder}
              AND status = 'active'
            ORDER BY episode_no, video_id
            """,
            (source_series_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def _get_source_danmaku(source_video_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                danmaku_id,
                video_id,
                user_id,
                client_time,
                time_ms,
                text,
                source,
                digg_count,
                score,
                status,
                raw_json
            FROM danmaku_items
            WHERE video_id = {placeholder}
              AND status = 'active'
            ORDER BY client_time, danmaku_id
            """,
            (source_video_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def _json_item(target_video_id: str, row: dict[str, Any]) -> dict[str, Any]:
    source_danmaku_id = str(row["danmaku_id"])
    return {
        "danmaku_id": _target_danmaku_id(target_video_id, source_danmaku_id),
        "source_danmaku_id": source_danmaku_id,
        "time_sec": float(row["client_time"]),
        "time_ms": int(row["time_ms"]),
        "text": str(row["text"]),
        "user_id": row.get("user_id"),
        "digg_count": int(row.get("digg_count") or 0),
        "score": float(row.get("score") or 0),
    }


def _danmaku_json_payload(
    *,
    source_video: dict[str, Any],
    target_series_id: str,
    target_video_id: str,
    target_object_key: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "metadata": {
            "storage_layout": "dramas/{series_id}/episodes/{episode_label}/danmaku/douyin.json",
            "source_series_id": source_video["series_id"],
            "source_video_id": source_video["video_id"],
            "target_series_id": target_series_id,
            "target_video_id": target_video_id,
            "target_object_key": target_object_key,
            "episode_no": source_video["episode_no"],
            "episode_label": source_video["episode_label"],
        },
        "danmaku": {
            "count": len(items),
            "items": items,
        },
    }


def _put_json_object(object_key: str, payload: dict[str, Any]) -> int:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    settings = get_settings()
    if settings.mode == "local":
        path = (settings.local_oss_root / object_key).resolve()
        root = settings.local_oss_root.resolve()
        if not path.is_relative_to(root):
            raise RuntimeError(f"Invalid local object key: {object_key}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return len(body)

    bucket = get_bucket(settings)
    bucket.put_object(object_key, body, headers={"Content-Type": "application/json; charset=utf-8"})
    return len(body)


def _upsert_target_video(source_video: dict[str, Any], *, target_series_id: str, target_series_name: str, object_prefix: str) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    episode_label = str(source_video["episode_label"])
    target_video_id = _target_video_id(target_series_id, episode_label)
    video_object_key = _episode_video_key(object_prefix, episode_label)
    danmaku_object_key = _episode_danmaku_key(object_prefix, episode_label)
    meta = get_object_meta(video_object_key, bucket_name=settings.oss_bucket if settings.mode != "local" else None)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    duration, oss_bucket, oss_object_key, douyin_video_id, douyin_json_path,
                    content_type, size, source, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'oss', 'active')
                ON CONFLICT(video_id) DO UPDATE SET
                    series_id = excluded.series_id,
                    series_name = excluded.series_name,
                    title = excluded.title,
                    episode_no = excluded.episode_no,
                    episode_label = excluded.episode_label,
                    duration = excluded.duration,
                    oss_bucket = excluded.oss_bucket,
                    oss_object_key = excluded.oss_object_key,
                    douyin_video_id = excluded.douyin_video_id,
                    douyin_json_path = excluded.douyin_json_path,
                    content_type = excluded.content_type,
                    size = excluded.size,
                    source = excluded.source,
                    status = excluded.status,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                (
                    target_video_id,
                    target_series_id,
                    target_series_name,
                    str(source_video["title"]),
                    source_video["episode_no"],
                    episode_label,
                    source_video["duration"],
                    settings.local_oss_bucket,
                    video_object_key,
                    source_video.get("douyin_video_id"),
                    danmaku_object_key,
                    meta.content_type or DEFAULT_CONTENT_TYPE,
                    meta.content_length,
                ),
            )
            return

        cursor.execute(
            f"""
            INSERT INTO videos (
                video_id, series_id, series_name, title, episode_no, episode_label,
                duration, oss_bucket, oss_object_key, douyin_video_id, douyin_json_path,
                content_type, size, source, status
            )
            VALUES (
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, 'oss', 'active'
            )
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
            (
                target_video_id,
                target_series_id,
                target_series_name,
                str(source_video["title"]),
                source_video["episode_no"],
                episode_label,
                source_video["duration"],
                settings.oss_bucket,
                video_object_key,
                source_video.get("douyin_video_id"),
                danmaku_object_key,
                meta.content_type or DEFAULT_CONTENT_TYPE,
                meta.content_length,
            ),
        )


def _upsert_target_danmaku(target_video_id: str, source_rows: list[dict[str, Any]]) -> int:
    if not source_rows:
        return 0

    settings = get_settings()
    placeholder = sql_placeholder(settings)
    rows: list[tuple[Any, ...]] = []
    for row in source_rows:
        source_danmaku_id = str(row["danmaku_id"])
        raw = json.loads(row["raw_json"]) if row.get("raw_json") else {}
        if isinstance(raw, dict):
            raw = {**raw, "source_video_id": row["video_id"], "source_danmaku_id": source_danmaku_id}
        rows.append(
            (
                _target_danmaku_id(target_video_id, source_danmaku_id),
                target_video_id,
                row.get("user_id"),
                row["client_time"],
                row["time_ms"],
                row["text"],
                "douyin_copy",
                row.get("digg_count") or 0,
                row.get("score") or 0,
                "active",
                json.dumps(raw, ensure_ascii=False),
            )
        )

    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.executemany(
                """
                INSERT INTO danmaku_items (
                    danmaku_id, video_id, user_id, client_time, time_ms, text,
                    source, digg_count, score, status, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(danmaku_id) DO UPDATE SET
                    video_id = excluded.video_id,
                    user_id = excluded.user_id,
                    client_time = excluded.client_time,
                    time_ms = excluded.time_ms,
                    text = excluded.text,
                    source = excluded.source,
                    digg_count = excluded.digg_count,
                    score = excluded.score,
                    status = excluded.status,
                    raw_json = excluded.raw_json
                """,
                rows,
            )
            return len(rows)

        cursor.executemany(
            f"""
            INSERT INTO danmaku_items (
                danmaku_id, video_id, user_id, client_time, time_ms, text,
                source, digg_count, score, status, raw_json
            )
            VALUES (
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}
            )
            ON DUPLICATE KEY UPDATE
                video_id = VALUES(video_id),
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
        return len(rows)


def prepare_experiment(
    *,
    source_series_id: str,
    target_series_id: str,
    target_object_prefix: str,
    target_series_name: str | None,
    dry_run: bool,
) -> dict[str, int]:
    settings = get_settings()
    if settings.mode == "cloud":
        require_complete_cloud_settings(settings)

    source_videos = _get_source_videos(source_series_id)
    if not source_videos:
        raise RuntimeError(f"No active source videos found for series_id={source_series_id}")

    resolved_target_series_name = target_series_name or f"{source_videos[0]['series_name']}{DEFAULT_TARGET_SERIES_NAME_SUFFIX}"
    prepared_videos = 0
    copied_items = 0
    uploaded_json = 0

    for source_video in source_videos:
        episode_label = str(source_video["episode_label"])
        target_video_id = _target_video_id(target_series_id, episode_label)
        target_danmaku_key = _episode_danmaku_key(target_object_prefix, episode_label)
        source_rows = _get_source_danmaku(str(source_video["video_id"]))
        json_items = [_json_item(target_video_id, row) for row in source_rows]
        payload = _danmaku_json_payload(
            source_video=source_video,
            target_series_id=target_series_id,
            target_video_id=target_video_id,
            target_object_key=target_danmaku_key,
            items=json_items,
        )

        print(
            f"{source_video['video_id']} -> {target_video_id}: "
            f"{len(source_rows)} danmaku, json={target_danmaku_key}"
        )
        if dry_run:
            continue

        _upsert_target_video(
            source_video,
            target_series_id=target_series_id,
            target_series_name=resolved_target_series_name,
            object_prefix=target_object_prefix,
        )
        _put_json_object(target_danmaku_key, payload)
        uploaded_json += 1
        copied_items += _upsert_target_danmaku(target_video_id, source_rows)
        prepared_videos += 1

    return {
        "source_videos": len(source_videos),
        "prepared_videos": prepared_videos,
        "uploaded_json": uploaded_json,
        "copied_danmaku_items": copied_items,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a non-destructive danmaku storage experiment under dramas/{series_id}/episodes/{episode_label}/danmaku/.",
    )
    parser.add_argument("--source-series-id", default=DEFAULT_SOURCE_SERIES_ID)
    parser.add_argument("--target-series-id", default=DEFAULT_TARGET_SERIES_ID)
    parser.add_argument("--target-object-prefix", default=DEFAULT_TARGET_OBJECT_PREFIX)
    parser.add_argument("--target-series-name", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    result = prepare_experiment(
        source_series_id=args.source_series_id,
        target_series_id=args.target_series_id,
        target_object_prefix=args.target_object_prefix.strip("/"),
        target_series_name=args.target_series_name,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

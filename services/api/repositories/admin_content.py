from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from ..config import Settings, get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql
from ..oss_client import get_bucket
from ..oss_client import read_object_range
from .assets import public_object_url
from .admin_analysis import latest_analysis_jobs_by_video


SERIES_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
VIDEO_CONTENT_TYPES = {"video/mp4", "application/mp4", "video/quicktime"}
DANMAKU_CONTENT_TYPES = {"application/json", "text/json", "application/octet-stream", ""}
DRAMA_OBJECT_KEY_PREFIX = "dramas/%"
MANAGED_VIDEO_STATUSES = ("active", "deleted")
CHUNK_UPLOAD_DIR = ".dramepulse_uploads"


def _validate_series_id(series_id: str) -> str:
    normalized = series_id.strip()
    if not SERIES_ID_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="series_id must contain only lowercase letters, numbers, underscores, or hyphens",
        )
    return normalized


def _episode_label(episode_no: int) -> str:
    if episode_no <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="episode_no must be positive")
    return f"ep{episode_no:02d}"


def _validate_episode_label(episode_label: str) -> str:
    normalized = episode_label.strip().lower()
    if not re.fullmatch(r"ep\d{2,}", normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="episode_label must use epXX format")
    return normalized


def _ensure_local_target(settings: Settings, object_key: str) -> Path:
    root = settings.local_oss_root.resolve()
    path = (root / object_key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid object key")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe_upload_id(upload_id: str) -> str:
    normalized = upload_id.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="upload_id is invalid")
    return normalized


def _chunk_upload_path(settings: Settings, upload_id: str) -> Path:
    root = (settings.local_oss_root / CHUNK_UPLOAD_DIR).resolve()
    path = (root / f"{upload_id}.part").resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload id")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _put_bytes(object_key: str, body: bytes, content_type: str) -> int:
    settings = get_settings()
    if settings.mode == "local":
        path = _ensure_local_target(settings, object_key)
        path.write_bytes(body)
        return path.stat().st_size

    bucket = get_bucket(settings)
    bucket.put_object(object_key, body, headers={"Content-Type": content_type})
    meta = bucket.head_object(object_key)
    return int(meta.headers.get("Content-Length", len(body)))


def _put_file(object_key: str, path: Path, content_type: str) -> int:
    settings = get_settings()
    if settings.mode == "local":
        target = _ensure_local_target(settings, object_key)
        target.write_bytes(path.read_bytes())
        return target.stat().st_size

    bucket = get_bucket(settings)
    with path.open("rb") as handle:
        bucket.put_object(object_key, handle, headers={"Content-Type": content_type})
    meta = bucket.head_object(object_key)
    return int(meta.headers.get("Content-Length", path.stat().st_size))


async def _read_upload(upload: UploadFile) -> bytes:
    body = await upload.read()
    if not body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")
    return body


def new_upload_id() -> str:
    return uuid4().hex


async def create_series(series_id: str, series_name: str) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    clean_series_name = series_name.strip()
    if not clean_series_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="series_name is required")

    object_key = f"dramas/{clean_series_id}/name.txt"
    body = clean_series_name.encode("utf-8")
    size = _put_bytes(object_key, body, "text/plain; charset=utf-8")
    _update_series_name(clean_series_id, clean_series_name)
    return {"series_id": clean_series_id, "series_name": clean_series_name, "name_object_key": object_key, "size": size}


def _series_keys(series_id: str) -> dict[str, str]:
    return {
        "name_object_key": f"dramas/{series_id}/name.txt",
        "cover_object_key": f"dramas/{series_id}/cover.jpg",
    }


def get_series_cover_storage(series_id: str) -> dict[str, Any] | None:
    clean_series_id = _validate_series_id(series_id)
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT cover_object_key, cover_content_type
            FROM series_assets
            WHERE series_id = {placeholder}
              AND status = 'active'
              AND cover_object_key IS NOT NULL
              AND cover_object_key <> ''
            """,
            (clean_series_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def _ensure_series_assets_table() -> None:
    settings = get_settings()
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS series_assets (
                    series_id TEXT PRIMARY KEY,
                    cover_object_key TEXT NULL,
                    cover_url TEXT NULL,
                    cover_content_type TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_assets_status ON series_assets (status)")
            return

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS series_assets (
                series_id VARCHAR(128) PRIMARY KEY,
                cover_object_key VARCHAR(512) NULL,
                cover_url VARCHAR(1024) NULL,
                cover_content_type VARCHAR(128) NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                KEY idx_series_assets_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _upsert_series_cover_asset(series_id: str, object_key: str, content_type: str) -> None:
    _ensure_series_assets_table()
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    cover_url = public_object_url(object_key)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO series_assets (
                    series_id, cover_object_key, cover_url, cover_content_type, status
                )
                VALUES (?, ?, ?, ?, 'active')
                ON CONFLICT(series_id) DO UPDATE SET
                    cover_object_key = excluded.cover_object_key,
                    cover_url = excluded.cover_url,
                    cover_content_type = excluded.cover_content_type,
                    status = excluded.status,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                (series_id, object_key, cover_url, content_type),
            )
            return

        cursor.execute(
            f"""
            INSERT INTO series_assets (
                series_id, cover_object_key, cover_url, cover_content_type, status
            )
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active')
            ON DUPLICATE KEY UPDATE
                cover_object_key = VALUES(cover_object_key),
                cover_url = VALUES(cover_url),
                cover_content_type = VALUES(cover_content_type),
                status = VALUES(status),
                updated_at = {now_sql}
            """,
            (series_id, object_key, cover_url, content_type),
        )


def read_series_cover(series_id: str) -> tuple[bytes, str] | None:
    storage = get_series_cover_storage(series_id)
    if storage is None:
        return None
    object_key = str(storage["cover_object_key"])
    content_type = str(storage.get("cover_content_type") or "image/jpeg")
    return read_object_range(object_key), content_type


def _update_series_name(series_id: str, series_name: str) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            UPDATE videos
            SET series_name = {placeholder},
                updated_at = {now_sql}
            WHERE series_id = {placeholder}
            """,
            (series_name, series_id),
        )


def list_series() -> list[dict[str, Any]]:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                series_id,
                MAX(series_name) AS series_name,
                CASE
                    WHEN SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) > 0 THEN 'active'
                    ELSE 'deleted'
                END AS status,
                COUNT(*) AS episode_count,
                MIN(episode_no) AS min_episode_no,
                MAX(episode_no) AS max_episode_no
            FROM videos
            WHERE status IN ({placeholder}, {placeholder})
              AND oss_object_key LIKE {placeholder}
              AND series_id IS NOT NULL
              AND series_id <> ''
            GROUP BY series_id
            ORDER BY
                CASE WHEN SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) > 0 THEN 0 ELSE 1 END,
                series_id
            """,
            (*MANAGED_VIDEO_STATUSES, DRAMA_OBJECT_KEY_PREFIX),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    for row in rows:
        row.update(_series_keys(str(row["series_id"])))
    return rows


def get_series_detail(series_id: str) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT
                series_id,
                MAX(series_name) AS series_name,
                CASE
                    WHEN SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) > 0 THEN 'active'
                    ELSE 'deleted'
                END AS status,
                COUNT(*) AS episode_count,
                MIN(episode_no) AS min_episode_no,
                MAX(episode_no) AS max_episode_no
            FROM videos
            WHERE status IN ({placeholder}, {placeholder})
              AND oss_object_key LIKE {placeholder}
              AND series_id = {placeholder}
            GROUP BY series_id
            """,
            (*MANAGED_VIDEO_STATUSES, DRAMA_OBJECT_KEY_PREFIX, clean_series_id),
        )
        series_row = cursor.fetchone()
        if not series_row:
            series = {
                "series_id": clean_series_id,
                "series_name": None,
                "status": "deleted",
                "episode_count": 0,
                "min_episode_no": None,
                "max_episode_no": None,
            }
        else:
            series = dict(series_row)
        cursor.execute(
            f"""
            SELECT
                video_id,
                title,
                episode_no,
                episode_label,
                oss_bucket,
                oss_object_key,
                douyin_json_path,
                content_type,
                size,
                status,
                updated_at
            FROM videos
            WHERE series_id = {placeholder}
              AND status IN ({placeholder}, {placeholder})
              AND oss_object_key LIKE {placeholder}
            ORDER BY episode_no IS NULL, episode_no, video_id
            """,
            (clean_series_id, *MANAGED_VIDEO_STATUSES, DRAMA_OBJECT_KEY_PREFIX),
        )
        episodes = [dict(row) for row in cursor.fetchall()]
    _attach_analysis_jobs(episodes)
    series.update(_series_keys(clean_series_id))
    return {"series": series, "episodes": episodes}


def _attach_analysis_jobs(episodes: list[dict[str, Any]]) -> None:
    jobs = latest_analysis_jobs_by_video([str(episode["video_id"]) for episode in episodes])
    for episode in episodes:
        job = jobs.get(str(episode["video_id"]))
        episode["analysis_status"] = str(job.get("status") if job else "not_started")
        episode["analysis_stage"] = job.get("stage") if job else None
        episode["analysis_job_id"] = job.get("job_id") if job else None
        episode["analysis_result_path"] = job.get("result_text_path") if job else None


def delete_series(series_id: str) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            UPDATE videos
            SET status = 'deleted',
                updated_at = {now_sql}
            WHERE series_id = {placeholder}
              AND status = 'active'
            """,
            (clean_series_id,),
        )
        deleted_count = int(cursor.rowcount or 0)
    if deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    return {"series_id": clean_series_id, "deleted_episode_count": deleted_count}


def restore_series(series_id: str) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            UPDATE videos
            SET status = 'active',
                updated_at = {now_sql}
            WHERE series_id = {placeholder}
              AND status = 'deleted'
            """,
            (clean_series_id,),
        )
        restored_count = int(cursor.rowcount or 0)
    if restored_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deleted series not found")
    return {"series_id": clean_series_id, "restored_episode_count": restored_count}


async def upload_series_cover(series_id: str, file: UploadFile) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    content_type = str(file.content_type or "").lower()
    extension = IMAGE_EXTENSIONS.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="cover must be image/jpeg, image/png, or image/webp",
        )

    object_key = f"dramas/{clean_series_id}/cover.{extension}"
    size = _put_bytes(object_key, await _read_upload(file), content_type)
    _upsert_series_cover_asset(clean_series_id, object_key, content_type)
    return {"object_key": object_key, "content_type": content_type, "size": size}


def _clean_danmaku_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    danmaku = payload.get("danmaku") or {}
    items = danmaku.get("items") if isinstance(danmaku, dict) else None
    if items is None and isinstance(payload.get("danmaku"), list):
        items = payload.get("danmaku")
    if not isinstance(items, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="danmaku JSON must contain danmaku.items")
    return [item for item in items if isinstance(item, dict) and str(item.get("text") or "").strip()]


def _danmaku_id(video_id: str, item: dict[str, Any], index: int) -> str:
    raw_id = str(item.get("danmaku_id") or item.get("id") or item.get("cid") or index).strip()
    return f"douyin_{video_id}_{raw_id}"[:64]


def _danmaku_row(video_id: str, item: dict[str, Any], index: int) -> tuple[Any, ...]:
    client_time = float(item.get("time_sec") or item.get("client_time") or 0)
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


def _upsert_danmaku(rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    settings = get_settings()
    placeholder = sql_placeholder(settings)
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
            return

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


def _set_video_danmaku_path(video_id: str, object_key: str) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            UPDATE videos
            SET douyin_json_path = {placeholder},
                updated_at = {now_sql}
            WHERE video_id = {placeholder}
            """,
            (object_key, video_id),
        )


async def upload_episode_danmaku(series_id: str, episode_label: str, file: UploadFile) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    clean_episode_label = _validate_episode_label(episode_label)
    content_type = str(file.content_type or "").lower()
    if content_type not in DANMAKU_CONTENT_TYPES and not str(file.filename or "").lower().endswith(".json"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="danmaku must be a JSON file")

    body = await _read_upload(file)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="danmaku JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="danmaku JSON must be an object")

    video_id = f"{clean_series_id}_{clean_episode_label}"
    object_key = f"dramas/{clean_series_id}/episodes/{clean_episode_label}/danmaku/douyin.json"
    items = _clean_danmaku_items(payload)
    rows = [_danmaku_row(video_id, item, index) for index, item in enumerate(items, start=1)]
    size = _put_bytes(object_key, body, "application/json; charset=utf-8")
    _set_video_danmaku_path(video_id, object_key)
    _upsert_danmaku(rows)
    return {
        "object_key": object_key,
        "content_type": "application/json",
        "size": size,
        "danmaku_count": len(rows),
    }


def _upsert_video(row: tuple[Any, ...]) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        if settings.mode == "local":
            cursor.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    duration, oss_bucket, oss_object_key, douyin_video_id, douyin_json_path,
                    content_type, size, source, status
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, ?, ?, 'oss', 'active')
                ON CONFLICT(video_id) DO UPDATE SET
                    series_id = excluded.series_id,
                    series_name = excluded.series_name,
                    title = excluded.title,
                    episode_no = excluded.episode_no,
                    episode_label = excluded.episode_label,
                    oss_bucket = excluded.oss_bucket,
                    oss_object_key = excluded.oss_object_key,
                    content_type = excluded.content_type,
                    size = excluded.size,
                    source = excluded.source,
                    status = excluded.status,
                    updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                """,
                row,
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
                NULL, {placeholder}, {placeholder}, NULL, NULL, {placeholder}, {placeholder}, 'oss', 'active'
            )
            ON DUPLICATE KEY UPDATE
                series_id = VALUES(series_id),
                series_name = VALUES(series_name),
                title = VALUES(title),
                episode_no = VALUES(episode_no),
                episode_label = VALUES(episode_label),
                oss_bucket = VALUES(oss_bucket),
                oss_object_key = VALUES(oss_object_key),
                content_type = VALUES(content_type),
                size = VALUES(size),
                source = VALUES(source),
                status = VALUES(status),
                updated_at = {now_sql}
            """,
            row,
        )


async def upload_episode_video(
    *,
    series_id: str,
    series_name: str,
    episode_no: int,
    title: str,
    video: UploadFile,
) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    clean_series_name = series_name.strip()
    clean_title = title.strip()
    if not clean_series_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="series_name is required")
    if not clean_title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="title is required")

    content_type = str(video.content_type or "").lower()
    if content_type not in VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="video must be an mp4 video")

    episode_label = _episode_label(episode_no)
    video_id = f"{clean_series_id}_{episode_label}"
    object_key = f"dramas/{clean_series_id}/episodes/{episode_label}/video.mp4"
    size = _put_bytes(object_key, await _read_upload(video), "video/mp4")
    settings = get_settings()
    _upsert_video(
        (
            video_id,
            clean_series_id,
            clean_series_name,
            clean_title,
            episode_no,
            episode_label,
            settings.oss_bucket if settings.mode != "local" else settings.local_oss_bucket,
            object_key,
            "video/mp4",
            size,
        )
    )
    return {
        "video_id": video_id,
        "series_id": clean_series_id,
        "series_name": clean_series_name,
        "episode_no": episode_no,
        "episode_label": episode_label,
        "title": clean_title,
        "object_key": object_key,
        "content_type": "video/mp4",
        "size": size,
    }


async def upload_episode_video_chunk(
    *,
    series_id: str,
    series_name: str,
    episode_no: int,
    title: str,
    upload_id: str,
    chunk_index: int,
    total_chunks: int,
    total_size: int,
    chunk: UploadFile,
) -> dict[str, Any]:
    clean_series_id = _validate_series_id(series_id)
    clean_series_name = series_name.strip()
    clean_title = title.strip()
    clean_upload_id = _safe_upload_id(upload_id)
    if not clean_series_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="series_name is required")
    if not clean_title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="title is required")
    if total_chunks <= 0 or chunk_index < 0 or chunk_index >= total_chunks:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="chunk index is invalid")
    if total_size <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="total_size must be positive")

    body = await _read_upload(chunk)
    settings = get_settings()
    upload_path = _chunk_upload_path(settings, clean_upload_id)
    current_size = upload_path.stat().st_size if upload_path.exists() else 0
    if chunk_index == 0 and current_size > 0:
        upload_path.write_bytes(b"")
        current_size = 0
    if current_size + len(body) > total_size:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="chunk data exceeds declared total_size")

    with upload_path.open("ab") as handle:
        handle.write(body)

    received_size = upload_path.stat().st_size
    is_complete = chunk_index == total_chunks - 1
    if not is_complete:
        return {
            "video_id": f"{clean_series_id}_{_episode_label(episode_no)}",
            "series_id": clean_series_id,
            "series_name": clean_series_name,
            "episode_no": episode_no,
            "episode_label": _episode_label(episode_no),
            "title": clean_title,
            "object_key": "",
            "content_type": "video/mp4",
            "size": received_size,
        }

    if received_size != total_size:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="uploaded chunks do not match total_size")

    episode_label = _episode_label(episode_no)
    video_id = f"{clean_series_id}_{episode_label}"
    object_key = f"dramas/{clean_series_id}/episodes/{episode_label}/video.mp4"
    size = _put_file(object_key, upload_path, "video/mp4")
    try:
        upload_path.unlink()
    except FileNotFoundError:
        pass
    _upsert_video(
        (
            video_id,
            clean_series_id,
            clean_series_name,
            clean_title,
            episode_no,
            episode_label,
            settings.oss_bucket if settings.mode != "local" else settings.local_oss_bucket,
            object_key,
            "video/mp4",
            size,
        )
    )
    return {
        "video_id": video_id,
        "series_id": clean_series_id,
        "series_name": clean_series_name,
        "episode_no": episode_no,
        "episode_label": episode_label,
        "title": clean_title,
        "object_key": object_key,
        "content_type": "video/mp4",
        "size": size,
    }

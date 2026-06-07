from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.api.config import Settings, get_settings
from services.api.db import db_cursor, sql_placeholder, utc_now_sql
from services.api.oss_client import get_bucket, read_object_range


def _target_rows(settings: Settings, *, video_ids: list[str], include_existing: bool, limit: int | None) -> list[dict[str, Any]]:
    placeholder = sql_placeholder(settings)
    filters = ["status = 'active'", "oss_object_key IS NOT NULL", "oss_object_key <> ''"]
    params: list[Any] = []
    if not include_existing:
        filters.append("(duration IS NULL OR duration <= 0)")
    if video_ids:
        filters.append(f"video_id IN ({', '.join([placeholder] * len(video_ids))})")
        params.extend(video_ids)
    limit_sql = ""
    if limit is not None:
        limit_sql = f" LIMIT {placeholder}"
        params.append(limit)

    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT video_id, series_id, episode_no, duration, oss_bucket, oss_object_key, size
            FROM videos
            WHERE {" AND ".join(filters)}
            ORDER BY series_id IS NULL, series_id, episode_no IS NULL, episode_no, video_id
            {limit_sql}
            """,
            tuple(params),
        )
        return [dict(row) for row in cursor.fetchall()]


def _download_object(settings: Settings, row: dict[str, Any], target: Path) -> None:
    object_key = str(row["oss_object_key"])
    if settings.mode == "local":
        target.write_bytes(read_object_range(object_key, bucket_name=row.get("oss_bucket")))
        return

    bucket = get_bucket(settings, bucket_name=str(row.get("oss_bucket") or settings.oss_bucket))
    remote = bucket.get_object(object_key)
    with target.open("wb") as handle:
        while True:
            chunk = remote.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def probe_duration_seconds(video_path: Path, *, ffprobe_bin: str = "ffprobe") -> float:
    try:
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffprobe not found: {ffprobe_bin}") from exc

    if result.returncode == 0:
        text = result.stdout.strip()
        if text and text.upper() != "N/A":
            duration = round(float(text), 3)
            if duration > 0:
                return duration

    return _probe_duration_with_opencv(video_path)


def _probe_duration_with_opencv(video_path: Path) -> float:
    try:
        import cv2
    except Exception as exc:  # pragma: no cover - fallback depends on optional runtime package.
        raise RuntimeError("ffprobe failed and opencv-python is not available") from exc

    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise RuntimeError(f"Failed to open video for duration probe: {video_path}")
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        if frame_count <= 0 or fps <= 0:
            raise RuntimeError(f"Invalid OpenCV duration metadata: frame_count={frame_count}, fps={fps}")
        return round(frame_count / fps, 3)
    finally:
        capture.release()


def _update_duration(settings: Settings, video_id: str, duration: float) -> None:
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            UPDATE videos
            SET duration = {placeholder},
                updated_at = {now_sql}
            WHERE video_id = {placeholder}
            """,
            (duration, video_id),
        )


def backfill_video_durations(
    *,
    apply: bool,
    video_ids: list[str],
    include_existing: bool,
    limit: int | None,
    ffprobe_bin: str,
) -> dict[str, Any]:
    settings = get_settings()
    rows = _target_rows(settings, video_ids=video_ids, include_existing=include_existing, limit=limit)
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="dramepulse_duration_") as temp_dir:
        temp_root = Path(temp_dir)
        for row in rows:
            video_id = str(row["video_id"])
            target = temp_root / f"{video_id}.mp4"
            item: dict[str, Any] = {
                "video_id": video_id,
                "old_duration": row.get("duration"),
                "oss_bucket": row.get("oss_bucket"),
                "oss_object_key": row.get("oss_object_key"),
                "status": "pending",
            }
            try:
                _download_object(settings, row, target)
                duration = probe_duration_seconds(target, ffprobe_bin=ffprobe_bin)
                item["new_duration"] = duration
                item["status"] = "updated" if apply else "dry_run"
                if apply:
                    _update_duration(settings, video_id, duration)
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = str(exc)
            finally:
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
            results.append(item)

    return {
        "apply": apply,
        "matched": len(rows),
        "succeeded": sum(1 for item in results if item["status"] in {"updated", "dry_run"}),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill videos.duration from the actual uploaded MP4 files.")
    parser.add_argument("--apply", action="store_true", help="Write probed durations to videos.duration. Omit for dry-run.")
    parser.add_argument("--video-id", action="append", default=[], help="Limit to one video_id. Can be repeated.")
    parser.add_argument("--include-existing", action="store_true", help="Also re-probe rows that already have duration > 0.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of rows to process.")
    parser.add_argument("--ffprobe-bin", default=shutil.which("ffprobe") or "ffprobe")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = backfill_video_durations(
        apply=args.apply,
        video_ids=list(args.video_id),
        include_existing=args.include_existing,
        limit=args.limit,
        ffprobe_bin=args.ffprobe_bin,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

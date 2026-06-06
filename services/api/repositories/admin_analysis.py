from __future__ import annotations

from datetime import UTC, datetime
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from ..config import Settings, get_settings
from ..db import db_cursor, sql_placeholder, utc_now_sql
from ..oss_client import read_object_range


ANALYSIS_STATUSES = {"not_started", "running", "completed", "failed"}
_ANALYSIS_SEMAPHORE = threading.Semaphore(1)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def _row_to_job(row: dict[str, Any] | None, *, video_id: str | None = None) -> dict[str, Any]:
    if row is None:
        return {
            "job_id": None,
            "video_id": video_id or "",
            "status": "not_started",
            "stage": "not_started",
            "output_dir": None,
            "result_text_path": None,
            "error_message": None,
            "started_at": None,
            "finished_at": None,
        }
    return {
        "job_id": row.get("job_id"),
        "video_id": row.get("video_id"),
        "status": row.get("status"),
        "stage": row.get("stage"),
        "output_dir": row.get("output_dir"),
        "result_text_path": row.get("result_text_path"),
        "error_message": row.get("error_message"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }


def create_analysis_table_sqlite(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_analysis_jobs (
            job_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            output_dir TEXT NULL,
            result_text_path TEXT NULL,
            error_message TEXT NULL,
            started_at TEXT NULL,
            finished_at TEXT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_analysis_jobs_video_status ON video_analysis_jobs (video_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_analysis_jobs_video_created ON video_analysis_jobs (video_id, created_at)")


def create_analysis_table_mysql(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_analysis_jobs (
            job_id VARCHAR(64) PRIMARY KEY,
            video_id VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL,
            stage VARCHAR(64) NOT NULL,
            output_dir VARCHAR(1024) NULL,
            result_text_path VARCHAR(1024) NULL,
            error_message TEXT NULL,
            started_at DATETIME(6) NULL,
            finished_at DATETIME(6) NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
            CONSTRAINT fk_video_analysis_jobs_video
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            KEY idx_video_analysis_jobs_video_status (video_id, status),
            KEY idx_video_analysis_jobs_video_created (video_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def ensure_analysis_table(settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    with db_cursor(resolved) as cursor:
        if resolved.mode == "local":
            create_analysis_table_sqlite(cursor)
        else:
            create_analysis_table_mysql(cursor)


def _video_row(video_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT video_id, series_id, episode_label, episode_no, oss_object_key, status
            FROM videos
            WHERE video_id = {placeholder}
              AND status = 'active'
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def _latest_job(video_id: str) -> dict[str, Any] | None:
    ensure_analysis_table()
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT job_id, video_id, status, stage, output_dir, result_text_path, error_message, started_at, finished_at
            FROM video_analysis_jobs
            WHERE video_id = {placeholder}
            ORDER BY created_at DESC, job_id DESC
            LIMIT 1
            """,
            (video_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def latest_analysis_job(video_id: str) -> dict[str, Any]:
    if _video_row(video_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return _row_to_job(_latest_job(video_id), video_id=video_id)


def latest_analysis_jobs_by_video(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not video_ids:
        return {}
    ensure_analysis_table()
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    markers = ", ".join([placeholder] * len(video_ids))
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT job_id, video_id, status, stage, output_dir, result_text_path, error_message, started_at, finished_at
            FROM video_analysis_jobs
            WHERE video_id IN ({markers})
            ORDER BY created_at DESC, job_id DESC
            """,
            tuple(video_ids),
        )
        jobs: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            item = dict(row)
            video_id = str(item["video_id"])
            if video_id not in jobs:
                jobs[video_id] = _row_to_job(item)
    return jobs


def create_analysis_job(video_id: str) -> dict[str, Any]:
    video = _video_row(video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    latest = _latest_job(video_id)
    if latest and latest.get("status") == "running":
        job = _row_to_job(latest)
        job["_created"] = False
        return job

    ensure_analysis_table()
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    job_id = f"vaj_{uuid4().hex}"
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            INSERT INTO video_analysis_jobs (
                job_id, video_id, status, stage, output_dir, result_text_path, error_message, started_at, finished_at
            )
            VALUES ({placeholder}, {placeholder}, 'running', 'queued', NULL, NULL, NULL, {now_sql}, NULL)
            """,
            (job_id, video_id),
        )
    job = latest_analysis_job(video_id)
    job["_created"] = True
    return job


def run_analysis_job(job_id: str) -> None:
    with _ANALYSIS_SEMAPHORE:
        _run_analysis_job_locked(job_id)


def _run_analysis_job_locked(job_id: str) -> None:
    settings = get_settings()
    job = _job_by_id(job_id)
    if job is None:
        return
    video = _video_row(str(job["video_id"]))
    if video is None:
        _mark_job_failed(job_id, "Video not found")
        return

    try:
        _mark_job_stage(job_id, "preparing")
        with tempfile.TemporaryDirectory(prefix=f"dramepulse_analysis_{job_id}_") as temp_dir:
            video_path = _prepare_video_file(settings, video, Path(temp_dir))
            output_dir = _artifact_output_dir(settings, video)
            output_dir.mkdir(parents=True, exist_ok=True)
            result_text_path = _result_text_path(settings, video)
            result_text_path.parent.mkdir(parents=True, exist_ok=True)

            _mark_job_paths(job_id, output_dir, result_text_path)
            _mark_job_stage(job_id, "running_video_analyzer")
            _run_video_analyzer(settings, video_path, output_dir)
            _mark_job_stage(job_id, "saving_result")
            fusion_path = output_dir / "fusion_result.md"
            if not fusion_path.is_file():
                raise RuntimeError(f"Missing expected fusion result: {fusion_path}")
            shutil.copyfile(fusion_path, result_text_path)
            _mark_job_completed(job_id)
    except Exception as exc:
        _mark_job_failed(job_id, str(exc))


def _job_by_id(job_id: str) -> dict[str, Any] | None:
    ensure_analysis_table()
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            SELECT job_id, video_id, status, stage, output_dir, result_text_path, error_message, started_at, finished_at
            FROM video_analysis_jobs
            WHERE job_id = {placeholder}
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def _episode_label(video: dict[str, Any]) -> str:
    label = str(video.get("episode_label") or "").strip()
    if label:
        return label
    episode_no = int(video.get("episode_no") or 1)
    return f"ep{episode_no:02d}"


def _series_id(video: dict[str, Any]) -> str:
    return str(video.get("series_id") or video["video_id"]).strip()


def _artifact_output_dir(settings: Settings, video: dict[str, Any]) -> Path:
    return settings.video_analyzer_result_root / _series_id(video) / _episode_label(video)


def _result_text_path(settings: Settings, video: dict[str, Any]) -> Path:
    return settings.video_analyzer_result_root / _series_id(video) / f"{_episode_label(video)}.txt"


def _prepare_video_file(settings: Settings, video: dict[str, Any], temp_dir: Path) -> Path:
    object_key = str(video.get("oss_object_key") or "")
    if not object_key:
        raise RuntimeError("Video object key is empty")
    if settings.mode == "local":
        path = (settings.local_oss_root / object_key).resolve()
        root = settings.local_oss_root.resolve()
        if not path.is_file() or not path.is_relative_to(root):
            raise RuntimeError(f"Local video file not found: {object_key}")
        return path

    target = temp_dir / "video.mp4"
    target.write_bytes(read_object_range(object_key))
    return target


def _run_video_analyzer(settings: Settings, video_path: Path, output_dir: Path) -> None:
    python = settings.video_analyzer_python.strip()
    if not python:
        raise RuntimeError("VIDEO_ANALYZER_PYTHON is not configured")
    if settings.video_analyzer_client == "openai_api":
        if not settings.video_analyzer_api_key:
            raise RuntimeError("VIDEO_ANALYZER_API_KEY is not configured")
        if not settings.video_analyzer_api_base:
            raise RuntimeError("VIDEO_ANALYZER_API_BASE is not configured")
        if not settings.video_analyzer_model:
            raise RuntimeError("VIDEO_ANALYZER_MODEL is not configured")

    command = [
        python,
        "-m",
        "video_analyzer.cli",
        str(video_path),
        "--output",
        str(output_dir),
        "--client",
        settings.video_analyzer_client,
        "--whisper-model",
        settings.video_analyzer_whisper_model,
        "--max-frames",
        str(settings.video_analyzer_max_frames),
    ]
    if settings.video_analyzer_client == "openai_api":
        command.extend(
            [
                "--api-key",
                settings.video_analyzer_api_key,
                "--api-url",
                settings.video_analyzer_api_base,
                "--model",
                settings.video_analyzer_model,
            ]
        )

    result = subprocess.run(
        command,
        cwd=settings.video_analyzer_project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        details = "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part)
        raise RuntimeError(details or f"video-analyzer exited with code {result.returncode}")


def _update_job(job_id: str, assignments: dict[str, Any]) -> None:
    settings = get_settings()
    placeholder = sql_placeholder(settings)
    now_sql = utc_now_sql(settings)
    columns = [f"{column} = {placeholder}" for column in assignments]
    values = list(assignments.values())
    with db_cursor(settings) as cursor:
        cursor.execute(
            f"""
            UPDATE video_analysis_jobs
            SET {", ".join(columns)},
                updated_at = {now_sql}
            WHERE job_id = {placeholder}
            """,
            (*values, job_id),
        )


def _mark_job_stage(job_id: str, stage: str) -> None:
    _update_job(job_id, {"stage": stage})


def _mark_job_paths(job_id: str, output_dir: Path, result_text_path: Path) -> None:
    _update_job(job_id, {"output_dir": str(output_dir), "result_text_path": str(result_text_path)})


def _mark_job_completed(job_id: str) -> None:
    _update_job(job_id, {"status": "completed", "stage": "completed", "error_message": None, "finished_at": _now_iso()})


def _mark_job_failed(job_id: str, message: str) -> None:
    _update_job(job_id, {"status": "failed", "stage": "failed", "error_message": message[:4000], "finished_at": _now_iso()})


def read_analysis_result(video_id: str) -> dict[str, Any]:
    job = latest_analysis_job(video_id)
    if job["status"] != "completed" or not job.get("result_text_path"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis result not found")
    path = Path(str(job["result_text_path"]))
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis result file not found")
    return {"video_id": video_id, "job": job, "content": path.read_text(encoding="utf-8")}


def list_analysis_artifacts(video_id: str) -> dict[str, Any]:
    job = latest_analysis_job(video_id)
    output_dir_value = job.get("output_dir")
    artifacts: list[dict[str, Any]] = []
    if output_dir_value:
        output_dir = Path(str(output_dir_value))
        if output_dir.is_dir():
            for path in sorted(item for item in output_dir.iterdir() if item.is_file()):
                artifacts.append({"name": path.name, "path": str(path), "size": path.stat().st_size})
    result_text_path = job.get("result_text_path")
    if result_text_path and Path(str(result_text_path)).is_file():
        path = Path(str(result_text_path))
        artifacts.insert(0, {"name": path.name, "path": str(path), "size": path.stat().st_size})
    return {"video_id": video_id, "job": job, "artifacts": artifacts}

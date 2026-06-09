from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.api.config import get_settings, require_complete_cloud_settings
from services.api.db import db_cursor, sql_placeholder
from services.api.oss_client import get_bucket
from services.api.repositories.assets import public_object_url
from services.api.scripts.init_db import create_asset_tables


DEFAULT_SOURCE_ROOT = Path(r"D:\XuPlace\bytedance\dramepulse_backend_handoff_storyboards_covers_api_doc")
SERIES_ID_MAP = {
    "jiali_jiawai": "jialijiawai",
    "nanian_dongzhi": "naniandonzhi",
    "tianxia_diyi_wanku": "tianxiadiyiwanku",
    "yunmiao_1": "yunmiao1",
}
COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _mapped_series_id(source_series_id: str) -> str:
    return SERIES_ID_MAP.get(source_series_id, source_series_id)


def _mapped_video_id(source_video_id: str) -> str:
    for source_series_id, target_series_id in SERIES_ID_MAP.items():
        prefix = f"{source_series_id}_"
        if source_video_id.startswith(prefix):
            return f"{target_series_id}_{source_video_id[len(prefix):]}"
    return source_video_id


def _object_url(object_key: str) -> str:
    return public_object_url(object_key)


def _content_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _load_existing_assets() -> tuple[set[str], set[str]]:
    settings = get_settings()
    with db_cursor(settings) as cursor:
        cursor.execute("SELECT DISTINCT series_id FROM videos WHERE series_id IS NOT NULL AND series_id <> '' AND status = 'active'")
        series_ids = {str(row["series_id"]) for row in cursor.fetchall()}
        cursor.execute("SELECT video_id FROM videos WHERE status = 'active'")
        video_ids = {str(row["video_id"]) for row in cursor.fetchall()}
    return series_ids, video_ids


def _cover_candidates(source_root: Path) -> list[dict[str, Any]]:
    cover_dir = source_root / "apps" / "player-demo" / "assets" / "covers"
    if not cover_dir.is_dir():
        raise FileNotFoundError(f"Missing cover directory: {cover_dir}")
    candidates = []
    for path in sorted(cover_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in COVER_EXTENSIONS:
            continue
        source_series_id = path.stem
        series_id = _mapped_series_id(source_series_id)
        object_key = f"dramas/{series_id}/cover{path.suffix.lower()}"
        candidates.append(
            {
                "source_series_id": source_series_id,
                "series_id": series_id,
                "path": path,
                "object_key": object_key,
                "content_type": _content_type(path),
            }
        )
    return candidates


def _storyboard_candidates(source_root: Path) -> list[dict[str, Any]]:
    storyboard_root = source_root / "output" / "storyboards"
    if not storyboard_root.is_dir():
        raise FileNotFoundError(f"Missing storyboard directory: {storyboard_root}")
    candidates = []
    for episode_dir in sorted(path for path in storyboard_root.iterdir() if path.is_dir()):
        manifest_path = episode_dir / "storyboard_manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_video_id = str(manifest.get("video_id") or episode_dir.name)
        video_id = _mapped_video_id(source_video_id)
        sheet_paths = sorted(episode_dir.glob("sheet_*.jpg"))
        object_prefix = f"storyboards/{video_id}"
        manifest_object_key = f"{object_prefix}/storyboard_manifest.json"
        candidates.append(
            {
                "source_video_id": source_video_id,
                "video_id": video_id,
                "episode_dir": episode_dir,
                "manifest_path": manifest_path,
                "manifest": manifest,
                "sheet_paths": sheet_paths,
                "object_prefix": object_prefix,
                "manifest_object_key": manifest_object_key,
            }
        )
    return candidates


def _rewrite_manifest(candidate: dict[str, Any]) -> dict[str, Any]:
    manifest = dict(candidate["manifest"])
    manifest["video_id"] = candidate["video_id"]
    rewritten_sheets = []
    for sheet in manifest.get("sheets") or []:
        sheet_name = Path(str(sheet.get("url") or "")).name
        rewritten = dict(sheet)
        rewritten["url"] = _object_url(f"{candidate['object_prefix']}/{sheet_name}")
        rewritten_sheets.append(rewritten)
    manifest["sheets"] = rewritten_sheets
    return manifest


def _put_file(bucket: Any, path: Path, object_key: str, content_type: str) -> None:
    bucket.put_object_from_file(object_key, str(path), headers={"Content-Type": content_type})


def _put_json(bucket: Any, object_key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    bucket.put_object(object_key, body, headers={"Content-Type": "application/json; charset=utf-8"})


def _ensure_tables() -> None:
    settings = get_settings()
    with db_cursor(settings) as cursor:
        create_asset_tables(cursor)


def _upsert_cover(series_id: str, object_key: str, content_type: str) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO series_assets (
                series_id, cover_object_key, cover_url, cover_content_type, status
            )
            VALUES (%s, %s, %s, %s, 'active')
            ON DUPLICATE KEY UPDATE
                cover_object_key = VALUES(cover_object_key),
                cover_url = VALUES(cover_url),
                cover_content_type = VALUES(cover_content_type),
                status = VALUES(status),
                updated_at = UTC_TIMESTAMP(6)
            """,
            (series_id, object_key, _object_url(object_key), content_type),
        )


def _upsert_storyboard(video_id: str, manifest_object_key: str, manifest: dict[str, Any]) -> None:
    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO video_storyboards (
                video_id,
                interval_seconds,
                frame_width,
                frame_height,
                columns_count,
                rows_count,
                manifest_object_key,
                manifest_json,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            ON DUPLICATE KEY UPDATE
                interval_seconds = VALUES(interval_seconds),
                frame_width = VALUES(frame_width),
                frame_height = VALUES(frame_height),
                columns_count = VALUES(columns_count),
                rows_count = VALUES(rows_count),
                manifest_object_key = VALUES(manifest_object_key),
                manifest_json = VALUES(manifest_json),
                status = VALUES(status),
                updated_at = UTC_TIMESTAMP(6)
            """,
            (
                video_id,
                float(manifest["interval_seconds"]),
                int(manifest["frame_width"]),
                int(manifest["frame_height"]),
                int(manifest["columns"]),
                int(manifest["rows"]),
                manifest_object_key,
                json.dumps(manifest, ensure_ascii=False),
            ),
        )


def build_report(source_root: Path) -> dict[str, Any]:
    existing_series_ids, existing_video_ids = _load_existing_assets()
    covers = _cover_candidates(source_root)
    storyboards = _storyboard_candidates(source_root)
    matched_covers = [item for item in covers if item["series_id"] in existing_series_ids]
    skipped_covers = [item for item in covers if item["series_id"] not in existing_series_ids]
    matched_storyboards = [item for item in storyboards if item["video_id"] in existing_video_ids]
    skipped_storyboards = [item for item in storyboards if item["video_id"] not in existing_video_ids]
    return {
        "matched_covers": matched_covers,
        "skipped_covers": skipped_covers,
        "matched_storyboards": matched_storyboards,
        "skipped_storyboards": skipped_storyboards,
    }


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "matched_covers": [f"{item['source_series_id']}->{item['series_id']}" for item in report["matched_covers"]],
        "skipped_covers": [f"{item['source_series_id']}->{item['series_id']}" for item in report["skipped_covers"]],
        "matched_storyboards": [f"{item['source_video_id']}->{item['video_id']}" for item in report["matched_storyboards"]],
        "skipped_storyboards": [f"{item['source_video_id']}->{item['video_id']}" for item in report["skipped_storyboards"]],
    }


def import_assets(source_root: Path, *, dry_run: bool) -> dict[str, Any]:
    settings = get_settings()
    if settings.mode != "cloud":
        raise RuntimeError("DRAMEPULSE_MODE must be cloud")
    require_complete_cloud_settings(settings)

    report = build_report(source_root)
    if dry_run:
        return summarize(report)

    _ensure_tables()
    bucket = get_bucket(settings)
    for item in report["matched_covers"]:
        _put_file(bucket, item["path"], item["object_key"], item["content_type"])
        _upsert_cover(item["series_id"], item["object_key"], item["content_type"])

    for item in report["matched_storyboards"]:
        manifest = _rewrite_manifest(item)
        for sheet_path in item["sheet_paths"]:
            _put_file(bucket, sheet_path, f"{item['object_prefix']}/{sheet_path.name}", "image/jpeg")
        _put_json(bucket, item["manifest_object_key"], manifest)
        _upsert_storyboard(item["video_id"], item["manifest_object_key"], manifest)

    summary = summarize(report)
    summary["imported_cover_count"] = len(report["matched_covers"])
    summary["imported_storyboard_count"] = len(report["matched_storyboards"])
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import handoff covers and storyboards into OSS and MySQL.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    result = import_assets(args.source_root, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

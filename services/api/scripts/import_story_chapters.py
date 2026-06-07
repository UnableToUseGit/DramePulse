from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from services.api.config import get_settings
from services.api.db import db_cursor, sql_placeholder
from services.api.repositories.story_chapters import (
    ensure_story_chapter_tables,
    upsert_series_alias,
    upsert_story_chapter_asset,
)


EPISODE_DIR_RE = re.compile(r"^(?P<series>.+)_ep(?P<episode>\d{1,4})$", re.IGNORECASE)
DEFAULT_ALIASES = {
    "nanian_dongzhi": "naniandonzhi",
    "naniandongzhi": "naniandonzhi",
    "naniandonzhi": "naniandonzhi",
}


@dataclass(frozen=True)
class ParsedSourceId:
    source_video_id: str
    source_series_id: str | None
    episode_no: int | None


@dataclass(frozen=True)
class FilePayload:
    text: str | None
    sha256: str | None
    parse_status: str
    parsed: Any
    error: str | None


def normalize_series_id(value: str) -> str:
    return re.sub(r"[_\-\s]+", "", value).lower()


def parse_source_id(source_video_id: str) -> ParsedSourceId:
    match = EPISODE_DIR_RE.fullmatch(source_video_id)
    if not match:
        return ParsedSourceId(source_video_id=source_video_id, source_series_id=None, episode_no=None)
    return ParsedSourceId(
        source_video_id=source_video_id,
        source_series_id=match.group("series").lower(),
        episode_no=int(match.group("episode")),
    )


def read_payload(path: Path) -> FilePayload:
    if not path.is_file():
        return FilePayload(text=None, sha256=None, parse_status="missing", parsed=None, error="file_missing")
    body = path.read_bytes()
    sha256 = hashlib.sha256(body).hexdigest()
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return FilePayload(text=None, sha256=sha256, parse_status="invalid_encoding", parsed=None, error=str(exc))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return FilePayload(text=text, sha256=sha256, parse_status="invalid_json", parsed=None, error=str(exc))
    return FilePayload(text=text, sha256=sha256, parse_status="valid", parsed=parsed, error=None)


def load_video_id_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("video-id-map must be a JSON object")
    return {str(key): str(value) for key, value in payload.items()}


def seed_default_aliases() -> None:
    for alias, canonical in DEFAULT_ALIASES.items():
        upsert_series_alias(alias, canonical, source="story_chapter_import", note="Default import alias")


def existing_videos() -> list[dict[str, Any]]:
    settings = get_settings()
    with db_cursor(settings) as cursor:
        cursor.execute(
            """
            SELECT video_id, series_id, episode_no, status
            FROM videos
            WHERE status = 'active'
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def series_aliases() -> dict[str, str]:
    settings = get_settings()
    try:
        with db_cursor(settings) as cursor:
            cursor.execute("SELECT alias_series_id, canonical_series_id FROM series_aliases")
            return {str(row["alias_series_id"]): str(row["canonical_series_id"]) for row in cursor.fetchall()}
    except Exception:
        return {}


def resolve_video_id(parsed: ParsedSourceId, video_map: dict[str, str], videos: list[dict[str, Any]], aliases: dict[str, str]) -> dict[str, Any]:
    if parsed.source_video_id in video_map:
        target = video_map[parsed.source_video_id]
        match = [video for video in videos if str(video["video_id"]) == target]
        return _resolved_from_matches(parsed, parsed.source_series_id, match, "manual_map")

    exact = [video for video in videos if str(video["video_id"]) == parsed.source_video_id]
    if exact:
        return _resolved_from_matches(parsed, str(exact[0].get("series_id") or parsed.source_series_id or ""), exact, "video_id")

    if parsed.source_series_id and parsed.episode_no is not None:
        canonical = aliases.get(parsed.source_series_id, DEFAULT_ALIASES.get(parsed.source_series_id, parsed.source_series_id))
        by_series_episode = [
            video
            for video in videos
            if str(video.get("series_id") or "") == canonical and video.get("episode_no") == parsed.episode_no
        ]
        if by_series_episode:
            return _resolved_from_matches(parsed, canonical, by_series_episode, "series_alias_episode")

        normalized = normalize_series_id(parsed.source_series_id)
        candidates = [
            video
            for video in videos
            if video.get("episode_no") == parsed.episode_no
            and normalize_series_id(str(video.get("series_id") or "")) == normalized
        ]
        if not candidates:
            candidates = [
                video
                for video in videos
                if video.get("episode_no") == parsed.episode_no
                and normalize_series_id(_series_from_video_id(str(video["video_id"]))) == normalized
            ]
        return _resolved_from_matches(parsed, parsed.source_series_id, candidates, "normalized_unique")

    return {
        "status": "unmatched",
        "match_strategy": "none",
        "video_id": None,
        "canonical_series_id": parsed.source_series_id,
        "candidate_video_ids": [],
        "error": "source id is not parseable and no manual mapping was provided",
    }


def _resolved_from_matches(
    parsed: ParsedSourceId,
    canonical_series_id: str | None,
    matches: list[dict[str, Any]],
    strategy: str,
) -> dict[str, Any]:
    if len(matches) == 1:
        return {
            "status": "matched",
            "match_strategy": strategy,
            "video_id": str(matches[0]["video_id"]),
            "canonical_series_id": canonical_series_id,
            "candidate_video_ids": [str(matches[0]["video_id"])],
            "error": None,
        }
    if not matches:
        return {
            "status": "unmatched",
            "match_strategy": strategy,
            "video_id": None,
            "canonical_series_id": canonical_series_id,
            "candidate_video_ids": [],
            "error": "no active video matched",
        }
    return {
        "status": "ambiguous",
        "match_strategy": strategy,
        "video_id": None,
        "canonical_series_id": canonical_series_id,
        "candidate_video_ids": [str(video["video_id"]) for video in matches],
        "error": "multiple active videos matched",
    }


def _series_from_video_id(video_id: str) -> str:
    parsed = parse_source_id(video_id)
    return parsed.source_series_id or video_id


def extract_chapters(video_id: str, payload: FilePayload) -> list[dict[str, Any]]:
    if payload.parse_status != "valid" or not isinstance(payload.parsed, dict):
        return []
    source_chapters = payload.parsed.get("story_chapters")
    if not isinstance(source_chapters, list):
        return []
    chapters: list[dict[str, Any]] = []
    for index, item in enumerate(source_chapters, start=1):
        if not isinstance(item, dict):
            continue
        start_time = item.get("start_time")
        end_time = item.get("end_time")
        if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
            continue
        chapter_id = str(item.get("chapter_id") or f"ch_{video_id}_{index:03d}")
        chapters.append(
            {
                "chapter_id": chapter_id,
                "video_id": video_id,
                "chapter_index": index,
                "start_time": float(start_time),
                "end_time": float(end_time),
                "title": _optional_string(item.get("title")),
                "summary": _optional_string(item.get("summary")),
                "reason": _optional_string(item.get("reason")),
                "source": "subtitle_scene_aligned",
                "raw_json": json.dumps(item, ensure_ascii=False),
            }
        )
    return chapters


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def iter_source_dirs(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.iterdir() if path.is_dir())


def import_story_chapters(source_root: Path, *, apply: bool = False, video_id_map: dict[str, str] | None = None) -> dict[str, Any]:
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)

    if apply:
        ensure_story_chapter_tables()
        seed_default_aliases()
    videos = existing_videos()
    aliases = {**DEFAULT_ALIASES, **series_aliases()}
    resolved_map = video_id_map or {}
    results: list[dict[str, Any]] = []
    applied = 0

    for source_dir in iter_source_dirs(source_root):
        source_video_id = source_dir.name
        parsed = parse_source_id(source_video_id)
        compact_path = source_dir / "story_chapters.json"
        debug_path = source_dir / "story_chapters.debug.json"
        compact = read_payload(compact_path)
        debug = read_payload(debug_path)
        resolved = resolve_video_id(parsed, resolved_map, videos, aliases)
        result = {
            "source_video_id": source_video_id,
            "source_series_id": parsed.source_series_id,
            "episode_no": parsed.episode_no,
            "compact_parse_status": compact.parse_status,
            "debug_parse_status": debug.parse_status,
            **resolved,
        }

        if apply and resolved["status"] == "matched":
            video_id = str(resolved["video_id"])
            chapters = extract_chapters(video_id, compact)
            asset = {
                "video_id": video_id,
                "source_video_id": source_video_id,
                "source_series_id": parsed.source_series_id,
                "canonical_series_id": resolved.get("canonical_series_id"),
                "episode_no": parsed.episode_no,
                "story_chapters_text": compact.text,
                "story_chapters_debug_text": debug.text,
                "story_chapters_sha256": compact.sha256,
                "story_chapters_debug_sha256": debug.sha256,
                "source_dir": str(source_dir),
                "compact_source_path": str(compact_path) if compact_path.is_file() else None,
                "debug_source_path": str(debug_path) if debug_path.is_file() else None,
                "compact_parse_status": compact.parse_status,
                "debug_parse_status": debug.parse_status,
                "import_error": compact.error or debug.error,
            }
            upsert_story_chapter_asset(asset, chapters)
            result["chapter_count"] = len(chapters)
            applied += 1
        else:
            result["chapter_count"] = len(extract_chapters(str(resolved.get("video_id") or source_video_id), compact))
        results.append(result)

    summary = {
        "source_root": str(source_root),
        "apply": apply,
        "total": len(results),
        "matched": sum(1 for item in results if item["status"] == "matched"),
        "unmatched": sum(1 for item in results if item["status"] == "unmatched"),
        "ambiguous": sum(1 for item in results if item["status"] == "ambiguous"),
        "invalid_compact_json": sum(1 for item in results if item["compact_parse_status"] != "valid"),
        "invalid_debug_json": sum(1 for item in results if item["debug_parse_status"] != "valid"),
        "applied": applied,
        "results": results,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import story chapter JSON files into DramePulse database.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--video-id-map", type=Path, default=None)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    summary = import_story_chapters(
        args.source_root,
        apply=bool(args.apply),
        video_id_map=load_video_id_map(args.video_id_map),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

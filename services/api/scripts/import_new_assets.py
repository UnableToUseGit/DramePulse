from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.api.repositories.new_assets import (
    ensure_new_asset_tables,
    upsert_ad_slots,
    upsert_plot_beat_asset,
    upsert_video_interaction_asset,
)
from services.api.scripts.import_story_chapters import (
    existing_videos,
    load_video_id_map,
    parse_source_id,
    read_payload,
    resolve_video_id,
    series_aliases,
)


def import_new_assets(root: Path, *, apply: bool = False, video_id_map: dict[str, str] | None = None) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    if apply:
        ensure_new_asset_tables()

    videos = existing_videos()
    aliases = series_aliases()
    video_map = video_id_map or {}
    plot_results = import_plot_beats(root / "plot_beat", apply=apply, videos=videos, aliases=aliases, video_map=video_map)
    interaction_results = import_interaction_assets(
        root / "interaction_plan",
        apply=apply,
        videos=videos,
        aliases=aliases,
        video_map=video_map,
    )
    ad_results = import_ad_assets(root / "广告", apply=apply)

    return {
        "source_root": str(root),
        "apply": apply,
        "plot_beats": summarize_results(plot_results),
        "interaction_assets": summarize_results(interaction_results),
        "ad_slots": ad_results,
        "results": {
            "plot_beats": plot_results,
            "interaction_assets": interaction_results,
        },
    }


def import_plot_beats(
    root: Path,
    *,
    apply: bool,
    videos: list[dict[str, Any]],
    aliases: dict[str, str],
    video_map: dict[str, str],
) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for source_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        source_video_id = source_dir.name
        parsed = parse_source_id(source_video_id)
        resolved = resolve_video_id(parsed, video_map, videos, aliases)
        payload = read_payload(source_dir / "plot_beats.json")
        debug = read_payload(source_dir / "plot_beats.debug.json")
        video_id = str(resolved.get("video_id") or source_video_id)
        beats = extract_plot_beats(video_id, payload)
        result = {
            "asset_type": "plot_beats",
            "source_video_id": source_video_id,
            "source_series_id": parsed.source_series_id,
            "episode_no": parsed.episode_no,
            "plot_beats_parse_status": payload.parse_status,
            "debug_parse_status": debug.parse_status,
            "item_count": len(beats),
            **resolved,
        }
        if apply and resolved["status"] == "matched":
            upsert_plot_beat_asset(
                {
                    "video_id": video_id,
                    "source_video_id": source_video_id,
                    "source_series_id": parsed.source_series_id,
                    "canonical_series_id": resolved.get("canonical_series_id"),
                    "episode_no": parsed.episode_no,
                    "plot_beats_text": payload.text,
                    "plot_beats_debug_text": debug.text,
                    "plot_beats_sha256": payload.sha256,
                    "plot_beats_debug_sha256": debug.sha256,
                    "source_dir": str(source_dir),
                    "plot_beats_source_path": str(source_dir / "plot_beats.json"),
                    "debug_source_path": str(source_dir / "plot_beats.debug.json")
                    if (source_dir / "plot_beats.debug.json").is_file()
                    else None,
                    "plot_beats_parse_status": payload.parse_status,
                    "debug_parse_status": debug.parse_status,
                    "import_error": payload.error or debug.error,
                },
                beats,
            )
            result["applied"] = True
        else:
            result["applied"] = False
        results.append(result)
    return results


def import_interaction_assets(
    root: Path,
    *,
    apply: bool,
    videos: list[dict[str, Any]],
    aliases: dict[str, str],
    video_map: dict[str, str],
) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    specs = [
        ("emotional_button", root / "emotional_button"),
        ("inner_voice_danmaku", root / "inner_voice"),
    ]
    for mode, mode_root in specs:
        if not mode_root.is_dir():
            continue
        for source_dir in sorted(path for path in mode_root.iterdir() if path.is_dir()):
            source_video_id = source_dir.name
            parsed = parse_source_id(source_video_id)
            resolved = resolve_video_id(parsed, video_map, videos, aliases)
            plan = read_payload(source_dir / "interaction_plan.json")
            selection = read_payload(source_dir / "inner_voice_selection.json")
            clusters = read_payload(source_dir / "semantic_clusters.json")
            video_id = str(resolved.get("video_id") or source_video_id)
            items = extract_interaction_items(video_id, mode, f"{video_id}:{mode}", plan)
            result = {
                "asset_type": "interaction_assets",
                "interaction_mode": mode,
                "source_video_id": source_video_id,
                "source_series_id": parsed.source_series_id,
                "episode_no": parsed.episode_no,
                "plan_parse_status": plan.parse_status,
                "selection_parse_status": selection.parse_status,
                "semantic_clusters_parse_status": clusters.parse_status,
                "item_count": len(items),
                **resolved,
            }
            if apply and resolved["status"] == "matched":
                upsert_video_interaction_asset(
                    {
                        "asset_id": f"{video_id}:{mode}",
                        "video_id": video_id,
                        "source_video_id": source_video_id,
                        "interaction_mode": mode,
                        "source_series_id": parsed.source_series_id,
                        "canonical_series_id": resolved.get("canonical_series_id"),
                        "episode_no": parsed.episode_no,
                        "plan_text": plan.text,
                        "selection_text": selection.text,
                        "semantic_clusters_text": clusters.text,
                        "plan_sha256": plan.sha256,
                        "selection_sha256": selection.sha256,
                        "semantic_clusters_sha256": clusters.sha256,
                        "source_dir": str(source_dir),
                        "plan_source_path": str(source_dir / "interaction_plan.json"),
                        "selection_source_path": str(source_dir / "inner_voice_selection.json")
                        if (source_dir / "inner_voice_selection.json").is_file()
                        else None,
                        "semantic_clusters_source_path": str(source_dir / "semantic_clusters.json")
                        if (source_dir / "semantic_clusters.json").is_file()
                        else None,
                        "plan_parse_status": plan.parse_status,
                        "selection_parse_status": selection.parse_status,
                        "semantic_clusters_parse_status": clusters.parse_status,
                        "import_error": plan.error or selection.error or clusters.error,
                    },
                    items,
                )
                result["applied"] = True
            else:
                result["applied"] = False
            results.append(result)
    return results


def import_ad_assets(root: Path, *, apply: bool) -> dict[str, Any]:
    item_path = root / "item.json"
    if not item_path.is_file():
        return {"available": False, "slot_count": 0, "applied": 0, "error": "item.json not found"}
    payload = read_payload(item_path)
    if payload.parse_status != "valid" or not isinstance(payload.parsed, dict):
        return {"available": False, "slot_count": 0, "applied": 0, "error": payload.error or payload.parse_status}
    series_id = str(payload.parsed.get("series_id") or "").strip()
    slots = payload.parsed.get("slots")
    if not series_id or not isinstance(slots, list):
        return {"available": False, "slot_count": 0, "applied": 0, "error": "series_id or slots missing"}
    valid_slots = [
        slot
        for slot in slots
        if isinstance(slot, dict)
        and slot.get("slot_id")
        and isinstance(slot.get("after_episode_no"), int)
        and isinstance(slot.get("ad"), dict)
        and slot["ad"].get("ad_id")
    ]
    if apply:
        upsert_ad_slots(
            series_id,
            valid_slots,
            str(item_path),
            str(root / "ads.mp4") if (root / "ads.mp4").is_file() else None,
        )
    return {
        "available": True,
        "series_id": series_id,
        "slot_count": len(valid_slots),
        "applied": len(valid_slots) if apply else 0,
        "video_file_exists": (root / "ads.mp4").is_file(),
    }


def extract_plot_beats(video_id: str, payload: Any) -> list[dict[str, Any]]:
    if payload.parse_status != "valid" or not isinstance(payload.parsed, dict):
        return []
    chapters = payload.parsed.get("chapter_plot_beats")
    if not isinstance(chapters, list):
        return []
    beats: list[dict[str, Any]] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id") or "")
        source_beats = chapter.get("plot_beats")
        if not chapter_id or not isinstance(source_beats, list):
            continue
        for index, beat in enumerate(source_beats, start=1):
            if not isinstance(beat, dict):
                continue
            start_time = beat.get("start_time")
            end_time = beat.get("end_time")
            if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
                continue
            beats.append(
                {
                    "beat_id": str(beat.get("beat_id") or f"pb_{chapter_id}_{index:03d}"),
                    "video_id": video_id,
                    "chapter_id": chapter_id,
                    "beat_index": index,
                    "beat_type": str(beat.get("beat_type") or "unknown"),
                    "start_time": float(start_time),
                    "end_time": float(end_time),
                    "summary": optional_string(beat.get("summary")),
                    "reason": optional_string(beat.get("reason")),
                    "raw_json": json.dumps(beat, ensure_ascii=False),
                }
            )
    return beats


def extract_interaction_items(video_id: str, mode: str, asset_id: str, payload: Any) -> list[dict[str, Any]]:
    if payload.parse_status != "valid" or not isinstance(payload.parsed, list):
        return []
    items: list[dict[str, Any]] = []
    for item in payload.parsed:
        if not isinstance(item, dict):
            continue
        trigger_time = item.get("trigger_time")
        expire_time = item.get("expire_time")
        if not item.get("interaction_id") or not isinstance(trigger_time, (int, float)) or not isinstance(expire_time, (int, float)):
            continue
        items.append(
            {
                "interaction_id": str(item["interaction_id"]),
                "video_id": video_id,
                "interaction_mode": mode,
                "trigger_time": float(trigger_time),
                "expire_time": float(expire_time),
                "duration_sec": float(item["duration_sec"]) if isinstance(item.get("duration_sec"), (int, float)) else None,
                "content": item.get("content") if isinstance(item.get("content"), dict) else {},
                "source_asset_id": asset_id,
            }
        )
    return items


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(results),
        "matched": sum(1 for item in results if item["status"] == "matched"),
        "unmatched": sum(1 for item in results if item["status"] == "unmatched"),
        "ambiguous": sum(1 for item in results if item["status"] == "ambiguous"),
        "applied": sum(1 for item in results if item.get("applied")),
        "total_items": sum(int(item.get("item_count") or 0) for item in results if item["status"] == "matched"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import NewAssets into DramePulse database.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--video-id-map", type=Path, default=None)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    summary = import_new_assets(
        args.source_root,
        apply=bool(args.apply),
        video_id_map=load_video_id_map(args.video_id_map),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

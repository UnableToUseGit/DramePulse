from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

from pipelines.expression_trigger.labels import (
    SUPPORTED_INTERACTION_MODES,
    SUPPORTED_PLOT_PRIMARY_EXPRESSIONS,
    SUPPORTED_SOURCE_TYPES,
    normalize_plot_primary_expression,
)
from pipelines.common import SubtitleSegment


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _iter_raw_items(raw: Any) -> tuple[list[Any], bool]:
    if isinstance(raw, dict):
        if isinstance(raw.get("expression_triggers"), list):
            return raw["expression_triggers"], False
        if isinstance(raw.get("triggers"), list):
            return raw["triggers"], False
        if isinstance(raw.get("highlights"), list):
            return raw["highlights"], True
    if isinstance(raw, list):
        return raw, False
    return [], False


def _normalize_source_type(value: Any, *, from_legacy_highlight: bool) -> str:
    if from_legacy_highlight:
        return "plot"
    source_type = _clean_text(value)
    return source_type if source_type in SUPPORTED_SOURCE_TYPES else ""


def _normalize_interaction_mode(value: Any, *, source_type: str) -> str:
    interaction_mode = "" if value is None else _clean_text(value)
    if not interaction_mode:
        interaction_mode = "finale_rating" if source_type == "finale_judgment" else "single_tap"
    return interaction_mode if interaction_mode in SUPPORTED_INTERACTION_MODES else ""


def parse_expression_triggers(raw: Any, *, video_id: str) -> list[dict[str, Any]]:
    items, from_legacy_highlight = _iter_raw_items(raw)
    now = _now_iso()
    triggers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            intensity = float(item.get("intensity", item.get("expression_intensity", 0.0)))
            confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0 or end_time <= start_time:
            continue
        if not 0.0 <= intensity <= 1.0 or not 0.0 <= confidence <= 1.0:
            continue

        source_type = _normalize_source_type(
            item.get("source_type") or item.get("highlight_type"),
            from_legacy_highlight=from_legacy_highlight,
        )
        if not source_type:
            continue
        interaction_mode = _normalize_interaction_mode(item.get("interaction_mode"), source_type=source_type)
        if not interaction_mode:
            continue

        primary_expression = normalize_plot_primary_expression(item.get("primary_expression") or item.get("emotion"))
        summary = "" if item.get("summary") is None else _clean_text(item.get("summary"))
        reason = "" if item.get("reason") is None else _clean_text(item.get("reason"))
        setup = "" if item.get("setup") is None else _clean_text(item.get("setup"))
        turning_point = "" if item.get("turning_point") is None else _clean_text(item.get("turning_point"))
        expression_release = "" if item.get("expression_release") is None else _clean_text(item.get("expression_release"))
        if not primary_expression:
            continue
        if source_type == "plot" and primary_expression not in SUPPORTED_PLOT_PRIMARY_EXPRESSIONS:
            continue

        payoff_time = float(item.get("payoff_time", item.get("cue_time", start_time + (end_time - start_time) / 2.0)))
        payoff_time = min(max(start_time, payoff_time), end_time)
        trigger = {
            "trigger_id": f"et_{video_id}_{len(triggers) + 1:03d}",
            "video_id": video_id,
            "candidate_id": _clean_text(item.get("candidate_id") or ""),
            "decision": _clean_text(item.get("decision") or ""),
            "role_in_arc": _clean_text(item.get("role_in_arc") or ""),
            "start_time": _round_time(start_time),
            "end_time": _round_time(end_time),
            "story_interval_start": _round_time(start_time),
            "story_interval_end": _round_time(end_time),
            "payoff_time": _round_time(payoff_time),
            "cue_time": _round_time(payoff_time),
            "source_type": source_type,
            "primary_expression": primary_expression,
            "interaction_mode": interaction_mode,
            "intensity": intensity,
            "confidence": confidence,
            "summary": summary,
            "setup": setup,
            "turning_point": turning_point,
            "expression_release": expression_release,
            "reason": reason,
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
            "status": _clean_text(item.get("status", "verified")) or "verified",
            "created_at": str(item.get("created_at", now)),
            "updated_at": str(item.get("updated_at", now)),
        }
        triggers.append(trigger)
    return triggers


def expression_trigger_to_highlight_asset(trigger: dict[str, Any], *, index: int) -> dict[str, Any]:
    video_id = str(trigger["video_id"])
    confidence = float(trigger["confidence"])
    return {
        "highlight_id": f"h_{video_id}_{index:03d}",
        "video_id": video_id,
        "start_time": float(trigger["start_time"]),
        "end_time": float(trigger["end_time"]),
        "highlight_type": str(trigger["source_type"]),
        "emotion": str(trigger["primary_expression"]),
        "intensity": float(trigger["intensity"]),
        "summary": str(trigger["summary"]),
        "setup": str(trigger.get("setup") or ""),
        "turning_point": str(trigger.get("turning_point") or ""),
        "expression_release": str(trigger.get("expression_release") or ""),
        "reason": str(trigger["reason"]),
        "confidence": confidence,
        "highlight_score": confidence,
        "status": str(trigger.get("status") or "verified"),
        "created_at": str(trigger.get("created_at") or _now_iso()),
        "updated_at": str(trigger.get("updated_at") or _now_iso()),
    }


def expression_triggers_to_highlight_assets(triggers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [expression_trigger_to_highlight_asset(trigger, index=index) for index, trigger in enumerate(triggers, start=1)]


def format_expression_subtitle_timeline_seconds(segments: list[SubtitleSegment]) -> str:
    lines = ["[SUBTITLE_TIMELINE]"]
    for segment in segments:
        text = " ".join(segment.text.split())
        lines.append(f"[{segment.start:.3f}-{segment.end:.3f}] {text}")
    lines.append("[/SUBTITLE_TIMELINE]")
    return "\n".join(lines)


def filter_triggers_within_duration(triggers: list[dict[str, Any]], *, duration_sec: float) -> list[dict[str, Any]]:
    if duration_sec <= 0:
        return triggers
    filtered: list[dict[str, Any]] = []
    for trigger in triggers:
        try:
            start_time = float(trigger["start_time"])
            end_time = float(trigger["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 <= start_time <= duration_sec and end_time <= duration_sec:
            filtered.append(trigger)
    return filtered


__all__ = [
    "expression_trigger_to_highlight_asset",
    "expression_triggers_to_highlight_assets",
    "filter_triggers_within_duration",
    "format_expression_subtitle_timeline_seconds",
    "parse_expression_triggers",
]

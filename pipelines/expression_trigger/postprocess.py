from __future__ import annotations

from typing import Any


def _trigger_quality_score(trigger: dict[str, Any]) -> float:
    try:
        intensity = float(trigger.get("intensity", 0.0))
    except (TypeError, ValueError):
        intensity = 0.0
    try:
        confidence = float(trigger.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return intensity * confidence


def _trigger_start_time(trigger: dict[str, Any]) -> float:
    try:
        return float(trigger["start_time"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def _trigger_end_time(trigger: dict[str, Any]) -> float:
    try:
        return float(trigger["end_time"])
    except (KeyError, TypeError, ValueError):
        return _trigger_start_time(trigger)


def consolidate_expression_triggers(
    triggers: list[dict[str, Any]],
    *,
    same_expression_gap_sec: float = 30.0,
    min_intensity: float = 0.6,
    min_confidence: float = 0.72,
    max_triggers: int | None = 4,
) -> list[dict[str, Any]]:
    if not triggers:
        return []

    filtered: list[dict[str, Any]] = []
    for trigger in triggers:
        try:
            intensity = float(trigger.get("intensity", 0.0))
            confidence = float(trigger.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if len(triggers) > 1 and (intensity < min_intensity or confidence < min_confidence):
            continue
        filtered.append(trigger)
    if not filtered:
        filtered = sorted(triggers, key=_trigger_quality_score, reverse=True)[:1]

    kept: list[dict[str, Any]] = []
    for trigger in sorted(filtered, key=lambda item: (_trigger_start_time(item), _trigger_end_time(item))):
        if not kept:
            kept.append(trigger)
            continue
        previous = kept[-1]
        same_expression = previous.get("primary_expression") == trigger.get("primary_expression")
        nearby = _trigger_start_time(trigger) - _trigger_end_time(previous) <= same_expression_gap_sec
        if same_expression and nearby:
            if _trigger_quality_score(trigger) > _trigger_quality_score(previous):
                kept[-1] = trigger
            continue
        kept.append(trigger)

    if max_triggers is not None and len(kept) > max_triggers:
        kept = sorted(kept, key=_trigger_quality_score, reverse=True)[:max_triggers]
    return sorted(kept, key=lambda item: (_trigger_start_time(item), str(item.get("trigger_id", ""))))

__all__ = [
    "consolidate_expression_triggers",
]

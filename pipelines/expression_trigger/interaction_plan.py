from __future__ import annotations

import re
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _round_time


DEFAULT_INTERACTION_DURATION_SEC = 5.0
INTERACTION_MODE = "emotional_button"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _episode_no(video_id: str) -> int:
    match = re.search(r"_ep(\d+)$", video_id)
    if not match:
        match = re.search(r"(\d+)$", video_id)
    return int(match.group(1)) if match else 0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_expression_interaction_plan(
    expression_triggers: list[dict[str, Any]],
    *,
    video_id: str,
    series_id: str,
    duration_sec: float = DEFAULT_INTERACTION_DURATION_SEC,
) -> list[dict[str, Any]]:
    episode_no = _episode_no(video_id)
    plan: list[dict[str, Any]] = []
    for trigger in expression_triggers:
        if not isinstance(trigger, dict):
            continue
        trigger_id = _clean_text(trigger.get("trigger_id"))
        if not trigger_id:
            continue
        trigger_time = _round_time(_safe_float(trigger.get("trigger_time")))
        if trigger_time < 0:
            continue
        interaction_id = f"ip_{video_id}_{len(plan) + 1:03d}"
        expression_type = _clean_text(trigger.get("expression_type"))
        plan.append(
            {
                "interaction_id": interaction_id,
                "video_id": video_id,
                "series_id": series_id,
                "episode_no": episode_no,
                "interaction_mode": INTERACTION_MODE,
                "trigger_time": trigger_time,
                "duration_sec": _round_time(duration_sec),
                "expire_time": _round_time(trigger_time + duration_sec),
                "content": {
                    "expression_type": expression_type,
                    "source_trigger_id": trigger_id,
                    "source_start_time": _round_time(_safe_float(trigger.get("start_time"))),
                    "source_end_time": _round_time(_safe_float(trigger.get("end_time"))),
                },
            }
        )
    return plan


__all__ = ["build_expression_interaction_plan"]

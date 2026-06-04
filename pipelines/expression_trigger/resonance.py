from __future__ import annotations

from typing import Any

from pipelines.expression_trigger.baseline_mllm import _round_time, normalize_plot_primary_expression
from pipelines.expression_trigger.postprocess import _trigger_start_time


RESONANCE_EMOTION_CONFIG = {
    "爽点": {"label": "爽到了", "icon": "flame", "feedback_text": "你也爽到了", "offset_sec": 0.5},
    "笑点": {"label": "笑死了", "icon": "laugh", "feedback_text": "你也笑了", "offset_sec": 0.2},
    "甜点": {"label": "磕到了", "icon": "heart", "feedback_text": "你也磕到了", "offset_sec": 0.8},
    "泪点": {"label": "泪目了", "icon": "tear", "feedback_text": "你也泪目了", "offset_sec": 1.5},
}


def _format_count(count: int) -> str:
    if count >= 10000:
        return f"{count / 10000:.1f}万"
    return str(count)


def build_resonance_cues(
    triggers: list[dict[str, Any]],
    *,
    duration_sec: float,
    default_duration_sec: float = 6.0,
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    sorted_triggers = sorted(
        triggers,
        key=lambda item: (_trigger_start_time(item), str(item.get("trigger_id", ""))),
    )
    for index, trigger in enumerate(sorted_triggers, start=1):
        emotion_type = normalize_plot_primary_expression(trigger.get("primary_expression"))
        config = RESONANCE_EMOTION_CONFIG.get(emotion_type)
        if config is None:
            continue
        try:
            payoff_time = float(trigger.get("payoff_time", trigger.get("cue_time", trigger.get("start_time", 0.0))))
        except (TypeError, ValueError):
            payoff_time = _trigger_start_time(trigger)
        ui_trigger_time = min(max(0.0, payoff_time + float(config["offset_sec"])), max(duration_sec, 0.0))
        try:
            intensity = float(trigger.get("intensity", 0.0))
            confidence = float(trigger.get("confidence", 0.0))
        except (TypeError, ValueError):
            intensity = 0.0
            confidence = 0.0
        base_count = int(round(8000 + max(0.0, min(intensity * confidence, 1.0)) * 90000))
        video_id = str(trigger.get("video_id") or "")
        cues.append(
            {
                "cue_id": f"res_{video_id}_{index:03d}",
                "video_id": video_id,
                "source_trigger_id": str(trigger.get("trigger_id") or ""),
                "ui_trigger_time": _round_time(ui_trigger_time),
                "duration_sec": _round_time(default_duration_sec),
                "emotion_type": emotion_type,
                "label": str(config["label"]),
                "icon": str(config["icon"]),
                "feedback_text": str(config["feedback_text"]),
                "base_count": base_count,
                "count_text": _format_count(base_count),
                "priority": index,
                "summary": str(trigger.get("summary") or ""),
            }
        )
    return cues

__all__ = [
    "RESONANCE_EMOTION_CONFIG",
    "build_resonance_cues",
]

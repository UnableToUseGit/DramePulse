from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.candidates import _format_frame_timestamps, _metadata_block


PLOT_BEAT_TYPES = {
    "conflict_start",
    "conflict_escalation",
    "face_slap",
    "payback",
    "reversal",
    "rescue_success",
    "relationship_advance",
    "family_emotional_payoff",
}


def build_plot_beat_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
    frame_timestamps_seconds: list[float],
) -> str:
    return "\n".join(
        [
            "## TASK",
            "You are the Plot Beat Branch of an expression-trigger pipeline.",
            "Find story-structure candidate intervals in a short-drama episode.",
            "Do not decide final expression triggers. Only output plot candidates.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            f"FRAME_TIMESTAMPS_SECONDS: {_format_frame_timestamps(frame_timestamps_seconds)}",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## CANDIDATE_TYPES",
            ", ".join(sorted(PLOT_BEAT_TYPES)),
            "",
            "## RULES",
            "- A candidate is a semantic time range, not a single point.",
            "- Use `start_time` for the required context start.",
            "- Use `end_time` for the semantic interval end.",
            "- Use `trigger_time` for the best possible expression trigger point if later accepted.",
            "- Include conflict starts and escalations when important, even if they may later be rejected.",
            "- Prefer recall over precision, but every candidate must be grounded in subtitles or frames.",
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `plot_candidates`.",
            "Each candidate must contain exactly these keys: `candidate_type`, `start_time`, `end_time`, `trigger_time`, `summary`, `setup`, `turning_point`, `payoff`, `evidence`.",
            "Output shape:",
            json.dumps(
                {
                    "plot_candidates": [
                        {
                            "candidate_type": "payback",
                            "start_time": 58.0,
                            "end_time": 72.0,
                            "trigger_time": 67.0,
                            "summary": "女主掀桌反击。",
                            "setup": "儿子被嫂子刁难。",
                            "turning_point": "女主到场掀桌。",
                            "payoff": "被欺负的一方夺回主动权。",
                            "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
                        }
                    ]
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "",
            "## SUBTITLE_TIMELINE",
            subtitles_timeline,
        ]
    )


def _iter_plot_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("plot_candidates"), list):
        return raw["plot_candidates"]
    if isinstance(raw, list):
        return raw
    return []


def _evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def parse_plot_beat_candidates(raw: Any, *, video_id: str, duration_sec: float) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _iter_plot_items(raw):
        if not isinstance(item, dict):
            continue
        candidate_type = _clean_text(item.get("candidate_type"))
        if candidate_type not in PLOT_BEAT_TYPES:
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            trigger_time = float(item["trigger_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if trigger_time < start_time or trigger_time > end_time:
            continue
        if duration_sec > 0 and end_time > duration_sec:
            continue
        candidates.append(
            {
                "candidate_id": f"plot_{video_id}_{len(candidates) + 1:03d}",
                "source_branch": "plot_beat",
                "candidate_type": candidate_type,
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "trigger_time": _round_time(trigger_time),
                "summary": _clean_text(item.get("summary")),
                "setup": _clean_text(item.get("setup")),
                "turning_point": _clean_text(item.get("turning_point")),
                "payoff": _clean_text(item.get("payoff")),
                "evidence": _evidence_list(item.get("evidence")),
            }
        )
    return candidates


__all__ = [
    "PLOT_BEAT_TYPES",
    "build_plot_beat_prompt",
    "parse_plot_beat_candidates",
]

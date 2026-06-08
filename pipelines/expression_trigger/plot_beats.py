from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.candidates import _metadata_block


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


PLOT_BEAT_TYPE_DEFINITIONS = [
    ("conflict_start", "A new central conflict is introduced or breaks out."),
    ("conflict_escalation", "An existing conflict becomes more serious through higher stakes, stronger action, or sharper opposition."),
    ("face_slap", "A character is publicly disproved, embarrassed, or defeated by facts, identity, ability, or outcome."),
    ("payback", "A previously pressured side actively strikes back, punishes, or gets justice."),
    ("reversal", "The story direction, power relation, or viewer expectation clearly flips."),
    ("rescue_success", "A character is successfully saved and the immediate crisis is resolved."),
    ("relationship_advance", "A relationship becomes closer, clearer, or enters a new stage."),
    ("family_emotional_payoff", "A family-related emotional setup pays off through a specific line or action."),
]


MAX_PLOT_BEAT_SECONDS = 15.0


def plot_beat_type_definitions_block() -> str:
    return "\n".join(f"- {beat_type}: {definition}" for beat_type, definition in PLOT_BEAT_TYPE_DEFINITIONS)


def build_plot_beat_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
) -> str:
    return "\n".join(
        [
            "## TASK",
            "You are a short-drama plot beat annotator.",
            "Find atomic story-state changes where the plot turns or meaningfully moves forward.",
            "Only output plot beat candidates. Do not judge audience reaction value.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## CANDIDATE_TYPES",
            plot_beat_type_definitions_block(),
            "",
            "## RULES",
            "- A plot beat is an atomic story-state change carried by one shot or one/two adjacent subtitle lines.",
            "- It is semantically point-like. `start_time` and `end_time` are only the evidence span that carries the beat.",
            "- Output the smallest possible interval that contains the concrete plot change.",
            "- Target 1-8 seconds. Use up to 15 seconds only when one long subtitle line or continuous shot carries the beat.",
            "- Use `start_time` for the start of the line/shot carrying the beat.",
            "- Use `end_time` for the end of the line/shot carrying the beat.",
            "- Include important conflict starts and escalations when they clearly move the plot.",
            "- Never output a whole phone call, whole argument, whole scene, or chapter-like arc. Select the exact line/action where the story state changes.",
            "- Do not include ordinary chatter, repeated argument, background exposition, or isolated jokes with no plot movement.",
            "- Prefer recall over precision, but every candidate must be grounded in subtitles or sampled frames.",
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `plot_candidates`.",
            "Each candidate must contain exactly these keys: `candidate_type`, `start_time`, `end_time`, `summary`, `reason`, `evidence`.",
            "Output shape:",
            json.dumps(
                {
                    "plot_candidates": [
                        {
                            "candidate_type": "payback",
                            "start_time": 58.0,
                            "end_time": 72.0,
                            "summary": "女主掀桌反击。",
                            "reason": "女主从被动受辱转为主动压制对方，剧情权力关系发生变化。",
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
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if end_time - start_time > MAX_PLOT_BEAT_SECONDS:
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
                "summary": _clean_text(item.get("summary") or ""),
                "reason": _clean_text(item.get("reason") or ""),
                "evidence": _evidence_list(item.get("evidence")),
            }
        )
    return candidates


__all__ = [
    "PLOT_BEAT_TYPES",
    "PLOT_BEAT_TYPE_DEFINITIONS",
    "MAX_PLOT_BEAT_SECONDS",
    "plot_beat_type_definitions_block",
    "build_plot_beat_prompt",
    "parse_plot_beat_candidates",
]

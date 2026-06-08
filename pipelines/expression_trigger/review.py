from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import (
    _clean_text,
    _round_time,
)
from pipelines.expression_trigger.labels import (
    SUPPORTED_PLOT_PRIMARY_EXPRESSIONS,
    normalize_plot_primary_expression,
)
from pipelines.expression_trigger.candidates import (
    _expression_definitions_block,
    _format_frame_timestamps,
    _metadata_block,
)


def _merge_time_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start_time, end_time in sorted(ranges):
        if not merged or start_time > merged[-1][1]:
            merged.append((start_time, end_time))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end_time))
    return merged


def build_filter_frame_timestamps(
    *,
    candidates: list[dict[str, Any]],
    duration_sec: float,
    interval_sec: float = 2.0,
    context_sec: float = 2.0,
    max_frames: int | None = 100,
) -> list[float]:
    if duration_sec <= 0:
        return []
    if interval_sec <= 0:
        raise ValueError("interval_sec must be positive")
    if context_sec < 0:
        raise ValueError("context_sec must be non-negative")

    ranges: list[tuple[float, float]] = []
    for candidate in candidates:
        try:
            raw_start_time = float(candidate["start_time"])
            raw_end_time = float(candidate["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if raw_end_time <= raw_start_time:
            continue
        start_time = max(0.0, raw_start_time - context_sec)
        end_time = min(duration_sec, raw_end_time + context_sec)
        if end_time > start_time:
            ranges.append((_round_time(start_time), _round_time(end_time)))

    timestamps: list[float] = []
    for start_time, end_time in _merge_time_ranges(ranges):
        current = start_time
        while current < end_time:
            timestamps.append(_round_time(current))
            if max_frames is not None and len(timestamps) >= max_frames:
                return timestamps
            current = round(current + interval_sec, 3)
    return timestamps


def _build_candidate_filter_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    frame_timestamps_seconds: list[float] | None = None,
) -> str:
    candidates_json = json.dumps({"expression_candidates": candidates}, ensure_ascii=False, separators=(",", ":"))
    return "\n".join(
        [
            "## TASK",
            "Review the provided candidate story intervals and keep only the moments where viewers would actually want to react immediately.",
            "Use the candidate list and the full subtitle timeline to judge whether each candidate contains a real viewer-reaction moment.",
            "Do not create new moments outside the provided candidates.",
            "The candidate list is intentionally high-recall. Be selective and reject weak, duplicated, setup-only, or aftermath-only candidates.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            f"LOCAL_FRAME_TIMESTAMPS_SECONDS: {_format_frame_timestamps(frame_timestamps_seconds or [])}",
            "You will receive sampled video frames from the candidate intervals listed below.",
            "All subtitle timestamps and output times are plain seconds, not MM:SS or HH:MM:SS.",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## CANDIDATES",
            candidates_json,
            "",
            "## DECISION RULES",
            "- Keep a candidate only if the story beat would plausibly make viewers react with one of the four allowed reactions.",
            "- Reject candidates that are only setup, exposition, hardship, danger relief, approval, recruitment, opportunity, generic support, curiosity, or ordinary plot progression.",
            "- A kept moment should have a clear release structure: setup -> turning point -> viewer reaction payoff.",
            "- If multiple nearby candidates belong to the same continuous emotional arc, keep only the strongest payoff moment.",
            "- If kept, refine `start_time`, `end_time`, and `cue_time` to the short viewer-reaction window inside the candidate interval.",
            "- `cue_time` should be the best moment to surface an interaction after the reaction payoff becomes understandable; do not place it before the payoff lands.",
            "- If rejected, omit it from `expression_triggers`.",
            "- `primary_expression` must be exactly one of: 爽点, 甜点, 泪点, 笑点.",
            "",
            "## PRIMARY_EXPRESSIONS",
            *_expression_definitions_block(),
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly these keys: `candidate_decisions`, `expression_triggers`.",
            "`candidate_decisions` must contain one object for every input candidate, including rejected candidates.",
            "Each candidate decision object must contain exactly these keys: `candidate_id`, `decision`, `primary_expression`, `role_in_arc`, `payoff_time`, `payoff_reason`, `decision_reason`.",
            "`decision` must be exactly `keep` or `reject`.",
            "`role_in_arc` must be exactly one of: setup, payoff, aftermath, duplicate, weak.",
            "`payoff_time` must be a number in seconds for kept payoff candidates; use 0.0 for rejected candidates.",
            "Rejected candidates must appear in `candidate_decisions`, but must not appear in `expression_triggers`.",
            "Candidate decision example:",
            '{"candidate_id":"cand_demo_ep01_001","decision":"reject","primary_expression":"泪点","role_in_arc":"setup","payoff_time":0.0,"payoff_reason":"","decision_reason":"This is emotional setup, not the payoff moment."}',
            "For kept candidates, each object must contain exactly these keys: `candidate_id`, `decision`, `role_in_arc`, `start_time`, `end_time`, `payoff_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `setup`, `turning_point`, `expression_release`, `reason`.",
            "Use this exact object template for every kept trigger, in this exact key order:",
            '{"candidate_id":"","decision":"keep","role_in_arc":"payoff","start_time":0.0,"end_time":0.0,"payoff_time":0.0,"source_type":"plot","primary_expression":"爽点","intensity":0.0,"confidence":0.0,"summary":"","setup":"","turning_point":"","expression_release":"","reason":""}',
            "Field constraints:",
            "- `source_type` must be `plot`.",
            "- `end_time` must be <= VIDEO_DURATION_SECONDS.",
            "- `payoff_time` must be within [start_time, end_time].",
            "- `intensity` and `confidence` must be numbers from 0.0 to 1.0.",
            "- Do not include any extra keys.",
            "",
            "## SUBTITLE_TIMELINE",
            subtitles_timeline,
        ]
    )


def parse_candidate_decisions(raw: Any, *, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_by_id = {str(candidate.get("candidate_id")): candidate for candidate in candidates}
    raw_decisions = raw.get("candidate_decisions") if isinstance(raw, dict) else None
    decisions: list[dict[str, Any]] = []
    if isinstance(raw_decisions, list):
        for item in raw_decisions:
            if not isinstance(item, dict):
                continue
            candidate_id = _clean_text(item.get("candidate_id"))
            if candidate_id not in candidate_by_id:
                continue
            decision = _clean_text(item.get("decision")).lower()
            if decision not in {"keep", "reject"}:
                continue
            fallback_expression = _clean_text(candidate_by_id[candidate_id].get("primary_expression"))
            primary_expression = normalize_plot_primary_expression(item.get("primary_expression")) or fallback_expression
            if primary_expression not in SUPPORTED_PLOT_PRIMARY_EXPRESSIONS:
                primary_expression = fallback_expression
            role_in_arc = _clean_text(item.get("role_in_arc") or "")
            if role_in_arc not in {"setup", "payoff", "aftermath", "duplicate", "weak"}:
                role_in_arc = "payoff" if decision == "keep" else "weak"
            try:
                payoff_time = _round_time(float(item.get("payoff_time", 0.0)))
            except (TypeError, ValueError):
                payoff_time = 0.0
            decisions.append(
                {
                    "candidate_id": candidate_id,
                    "decision": decision,
                    "primary_expression": primary_expression,
                    "role_in_arc": role_in_arc,
                    "payoff_time": payoff_time,
                    "payoff_reason": _clean_text(item.get("payoff_reason") or ""),
                    "decision_reason": _clean_text(item.get("decision_reason") or ""),
                }
            )
    seen_ids = {decision["candidate_id"] for decision in decisions}
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id"))
        if candidate_id in seen_ids:
            continue
        decisions.append(
            {
                "candidate_id": candidate_id,
                "decision": "keep",
                "primary_expression": normalize_plot_primary_expression(candidate.get("primary_expression")),
                "role_in_arc": "payoff",
                "payoff_time": 0.0,
                "payoff_reason": "",
                "decision_reason": "",
            }
        )
    return decisions

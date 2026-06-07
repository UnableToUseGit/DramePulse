from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time


SUPPORTED_FINAL_EXPRESSIONS = {"爽点", "甜点", "泪点", "笑点"}


def build_triggerability_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    candidates: list[dict[str, Any]],
    top_k: int,
    min_gap_seconds: float,
) -> str:
    candidates_json = json.dumps({"candidates": candidates}, ensure_ascii=False, separators=(",", ":"))
    return "\n".join(
        [
            "## TASK",
            "You are the Triggerability Judge of a dual-branch expression-trigger pipeline.",
            "Decide which candidates can become final player expression triggers.",
            "You must judge semantic triggerability, final expression type, importance ranking, and timing refinement.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            f"SELECTION_LIMITS: top_k={top_k}, min_gap_seconds={min_gap_seconds:.3f}",
            "",
            "## FINAL_EXPRESSIONS",
            "- 爽点: active payback, face-slap, regaining power, or punishing the unfair side.",
            "- 甜点: relationship advance, confession, intimacy, or mutual care becoming clear.",
            "- 泪点: family/love/sacrifice/guardianship/understanding payoff.",
            "- 笑点: punchline, comic reversal, awkward misunderstanding, or exaggerated wording/action.",
            "",
            "## RULES",
            "- Keep only candidates whose semantic content can naturally become one of the four final expressions.",
            "- Reject unsupported shock-only moments instead of forcing them into 笑点.",
            "- Reject setup-only conflict starts or escalations without expression payoff.",
            "- Refine `start_time`, `end_time`, and `trigger_time` when needed.",
            "- `trigger_time` must be the best single player trigger time after the expression is understandable.",
            "- Score all kept candidates with `importance_score` from 0.0 to 1.0.",
            "",
            "## CANDIDATES",
            candidates_json,
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `triggerability_decisions`.",
            "Each decision must contain exactly these keys: `candidate_id`, `decision`, `expression_type`, `importance_score`, `start_time`, `end_time`, `trigger_time`, `reason`, `rank_reason`.",
            json.dumps(
                {
                    "triggerability_decisions": [
                        {
                            "candidate_id": "plot_demo_ep01_001",
                            "decision": "keep",
                            "expression_type": "爽点",
                            "importance_score": 0.91,
                            "start_time": 10.0,
                            "end_time": 20.0,
                            "trigger_time": 18.5,
                            "reason": "反击完成，解气明确。",
                            "rank_reason": "本集强爽点。",
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


def _iter_decision_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("triggerability_decisions"), list):
        return raw["triggerability_decisions"]
    if isinstance(raw, list):
        return raw
    return []


def _candidate_by_id(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(candidate.get("candidate_id") or ""): candidate for candidate in candidates if candidate.get("candidate_id")}


def _reject_decision(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id") or "")
    return {
        "candidate_id": candidate_id,
        "source_branch": str(candidate.get("source_branch") or ""),
        "candidate_type": str(candidate.get("candidate_type") or ""),
        "decision": "reject",
        "expression_type": "",
        "importance_score": 0.0,
        "start_time": float(candidate.get("start_time", 0.0) or 0.0),
        "end_time": float(candidate.get("end_time", 0.0) or 0.0),
        "trigger_time": float(candidate.get("trigger_time", 0.0) or 0.0),
        "summary": str(candidate.get("summary") or ""),
        "reason": reason,
        "rank_reason": "",
    }


def parse_triggerability_decisions(raw: Any, *, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates_by_id = _candidate_by_id(candidates)
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _iter_decision_items(raw):
        if not isinstance(item, dict):
            continue
        candidate_id = _clean_text(item.get("candidate_id"))
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None or candidate_id in seen:
            continue
        seen.add(candidate_id)
        expression_type = _clean_text(item.get("expression_type"))
        decision = _clean_text(item.get("decision")).lower()
        try:
            start_time = float(item.get("start_time", candidate.get("start_time")))
            end_time = float(item.get("end_time", candidate.get("end_time")))
            trigger_time = float(item.get("trigger_time", candidate.get("trigger_time")))
            importance_score = float(item.get("importance_score", 0.0))
        except (TypeError, ValueError):
            decisions.append(_reject_decision(candidate, "invalid triggerability timing or score"))
            continue
        invalid_time = start_time < 0.0 or end_time <= start_time or trigger_time < start_time or trigger_time > end_time
        unsupported = expression_type not in SUPPORTED_FINAL_EXPRESSIONS
        if decision != "keep" or invalid_time or unsupported:
            if invalid_time:
                reason = "invalid triggerability timing"
            elif unsupported:
                reason = "unsupported expression type"
            else:
                reason = _clean_text(item.get("reason")) or "candidate rejected by triggerability judge"
            decisions.append(_reject_decision(candidate, reason))
            continue
        decisions.append(
            {
                "candidate_id": candidate_id,
                "source_branch": str(candidate.get("source_branch") or ""),
                "candidate_type": str(candidate.get("candidate_type") or ""),
                "decision": "keep",
                "expression_type": expression_type,
                "importance_score": max(0.0, min(1.0, importance_score)),
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "trigger_time": _round_time(trigger_time),
                "summary": _clean_text(item.get("summary") or candidate.get("summary")),
                "reason": _clean_text(item.get("reason")),
                "rank_reason": _clean_text(item.get("rank_reason")),
            }
        )
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id and candidate_id not in seen:
            decisions.append(_reject_decision(candidate, "missing triggerability decision"))
    return decisions


def _decision_score(decision: dict[str, Any]) -> float:
    try:
        return float(decision.get("importance_score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _decision_trigger_time(decision: dict[str, Any]) -> float:
    try:
        return float(decision["trigger_time"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def select_top_expression_triggers(
    decisions: list[dict[str, Any]],
    *,
    video_id: str,
    top_k: int | None = 4,
    min_gap_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    keep_decisions = [decision for decision in decisions if decision.get("decision") == "keep"]
    selected: list[dict[str, Any]] = []
    for decision in sorted(keep_decisions, key=lambda item: (_decision_score(item), -_decision_trigger_time(item)), reverse=True):
        expression_type = str(decision.get("expression_type") or "")
        trigger_time = _decision_trigger_time(decision)
        duplicate_index: int | None = None
        for index, existing in enumerate(selected):
            if str(existing.get("expression_type") or "") != expression_type:
                continue
            if abs(trigger_time - _decision_trigger_time(existing)) <= min_gap_seconds:
                duplicate_index = index
                break
        if duplicate_index is not None:
            continue
        selected.append(decision)
        if top_k is not None and len(selected) >= top_k:
            break

    final: list[dict[str, Any]] = []
    for index, decision in enumerate(sorted(selected, key=lambda item: (_decision_trigger_time(item), str(item.get("candidate_id", "")))), start=1):
        final.append(
            {
                "trigger_id": f"et_{video_id}_{index:03d}",
                "video_id": video_id,
                "candidate_id": str(decision.get("candidate_id") or ""),
                "source_branch": str(decision.get("source_branch") or ""),
                "candidate_type": str(decision.get("candidate_type") or ""),
                "start_time": float(decision.get("start_time", 0.0)),
                "end_time": float(decision.get("end_time", 0.0)),
                "trigger_time": float(decision.get("trigger_time", 0.0)),
                "expression_type": str(decision.get("expression_type") or ""),
                "importance_score": float(decision.get("importance_score", 0.0)),
                "summary": str(decision.get("summary") or ""),
                "reason": str(decision.get("reason") or ""),
            }
        )
    return final


__all__ = [
    "SUPPORTED_FINAL_EXPRESSIONS",
    "build_triggerability_prompt",
    "parse_triggerability_decisions",
    "select_top_expression_triggers",
]

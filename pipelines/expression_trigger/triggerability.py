from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time


SUPPORTED_FINAL_EXPRESSIONS = {"爽点", "甜点", "泪点", "笑点"}
RUBRIC_SCORE_KEYS = (
    "semantic_fit",
    "emotional_release",
    "viewer_impulse",
    "type_specific",
)
MAX_TOTAL_SCORE = len(RUBRIC_SCORE_KEYS) * 2
MIN_TOTAL_SCORE_TO_KEEP = 7


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
            "Score every candidate with a fixed rubric for player expression trigger suitability.",
            "Do not decide keep/reject and do not rank or perform top-k selection. Downstream code will do that deterministically.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "",
            "## FINAL_EXPRESSIONS",
            "- 爽点: a hated antagonist, bully, oppressor, or unfair side first hurts/humiliates/suppresses the protagonist or sympathetic side, then gets counterattacked, exposed, face-slapped, punished, loses power, or publicly eats the loss.",
            "- 甜点: romantic or intimate payoff such as confession, kissing, couple-like care, mutual protection, relationship confirmation, or clear romantic warmth.",
            "- 泪点: accumulated family/love/sacrifice/guardianship/waiting/guilt/understanding emotion pays off through one concrete line or action.",
            "- 笑点: a clear comedic mechanism such as punchline, comic reveal, comic reversal, awkward misunderstanding, absurd wording/action, or sharp teasing.",
            "",
            "## RULES",
            "- Judge every candidate independently.",
            "- Do not perform top-k selection, do not enforce min_gap, and do not omit low-quality candidates.",
            "- If a candidate does not fit any final expression, set `expression_type` to `none` and use low rubric scores.",
            "- 爽点 requires a hated antagonist/oppressor and a payoff where that side is countered, defeated, embarrassed, or punished. Mere justice, benevolent repayment, a kind boss solving a debt, misunderstanding resolution, or things simply getting better is not 爽点.",
            "- 泪点 requires emotional accumulation and release; ordinary family logistics, casual care, or merely sending money home is not enough.",
            "- 笑点 requires a specific joke mechanism; do not treat sincere family or moving dialogue as comedy.",
            "- 甜点 is mainly romantic/intimate; ordinary friendship, family warmth, or generic relationship improvement is not enough.",
            "- Positive resolutions that do not fit any of the four expression types should be scored low instead of forcing a label.",
            "- Unsupported shock-only moments should be scored low instead of forcing them into 笑点.",
            "- Setup-only conflict starts or escalations without expression payoff should be scored low.",
            "- Do not output or adjust timing fields. Timing refinement is handled by a separate downstream step.",
            "",
            "## RUBRIC_SCORES",
            "Each score must be an integer 0, 1, or 2.",
            "- semantic_fit: 0=no valid final expression, 1=partial/ambiguous fit, 2=precise fit.",
            "- emotional_release: 0=setup/transition/logistics only, 1=some emotional value, 2=clear release/payoff.",
            "- viewer_impulse: 0=viewer unlikely to tap, 1=moderate impulse, 2=strong immediate impulse.",
            "- type_specific: 0=misses the core mechanism, 1=weak mechanism, 2=strong mechanism for the chosen type.",
            "",
            "## CANDIDATES",
            candidates_json,
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `triggerability_decisions`.",
            "Each decision must contain exactly these keys: `candidate_id`, `expression_type`, `rubric_scores`, `disqualifier`, `reason`.",
            json.dumps(
                {
                    "triggerability_decisions": [
                        {
                            "candidate_id": "plot_demo_ep01_001",
                            "expression_type": "爽点",
                            "rubric_scores": {
                                "semantic_fit": 2,
                                "emotional_release": 2,
                                "viewer_impulse": 2,
                                "type_specific": 2,
                            },
                            "disqualifier": "",
                            "reason": "反击完成，解气明确。",
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
    if isinstance(raw, dict):
        for key in ("triggerability_decisions", "rubric_evaluations", "rubric_decisions", "decisions", "evaluations"):
            if isinstance(raw.get(key), list):
                return raw[key]
    if isinstance(raw, list):
        return raw
    return []


def _candidate_by_id(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    candidates_by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for key in ("candidate_id", "source_beat_id", "beat_id"):
            candidate_id = str(candidate.get(key) or "")
            if candidate_id:
                candidates_by_id[candidate_id] = candidate
    return candidates_by_id


def _item_candidate_id(item: dict[str, Any]) -> str:
    for key in ("candidate_id", "source_beat_id", "beat_id", "plot_beat_id"):
        raw_candidate_id = item.get(key)
        if raw_candidate_id is None:
            continue
        candidate_id = _clean_text(raw_candidate_id)
        if candidate_id:
            return candidate_id
    return ""


def _reject_decision(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id") or "")
    return {
        "candidate_id": candidate_id,
        "source_branch": str(candidate.get("source_branch") or ""),
        "candidate_type": str(candidate.get("candidate_type") or ""),
        "decision": "reject",
        "expression_type": "",
        "rubric_scores": {key: 0 for key in RUBRIC_SCORE_KEYS},
        "total_score": 0,
        "importance_score": 0.0,
        "start_time": float(candidate.get("start_time", 0.0) or 0.0),
        "end_time": float(candidate.get("end_time", 0.0) or 0.0),
        "trigger_time": float(candidate.get("trigger_time", 0.0) or 0.0),
        "disqualifier": reason,
        "summary": str(candidate.get("summary") or ""),
        "reason": reason,
        "rank_reason": "",
    }


def _parse_rubric_scores(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    scores: dict[str, int] = {}
    for key in RUBRIC_SCORE_KEYS:
        try:
            score = int(value[key])
        except (KeyError, TypeError, ValueError):
            return None
        if score < 0 or score > 2:
            return None
        scores[key] = score
    return scores


def _total_score(scores: dict[str, int]) -> int:
    return sum(scores[key] for key in RUBRIC_SCORE_KEYS)


def _candidate_timing(candidate: dict[str, Any]) -> tuple[float, float, float] | None:
    try:
        start_time = float(candidate["start_time"])
        end_time = float(candidate["end_time"])
        trigger_time = float(candidate.get("trigger_time", end_time))
    except (KeyError, TypeError, ValueError):
        return None
    if start_time < 0.0 or end_time <= start_time:
        return None
    trigger_time = min(max(start_time, trigger_time), end_time)
    return _round_time(start_time), _round_time(end_time), _round_time(trigger_time)


def parse_triggerability_decisions(raw: Any, *, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates_by_id = _candidate_by_id(candidates)
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _iter_decision_items(raw):
        if not isinstance(item, dict):
            continue
        candidate_id = _item_candidate_id(item)
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None or candidate_id in seen:
            continue
        seen.add(candidate_id)
        expression_type = _clean_text(item.get("expression_type"))
        if expression_type.lower() == "none":
            expression_type = ""
        rubric_scores = _parse_rubric_scores(item.get("rubric_scores"))
        if rubric_scores is None:
            decisions.append(_reject_decision(candidate, "invalid rubric scores"))
            continue
        candidate_timing = _candidate_timing(candidate)
        if candidate_timing is None:
            decisions.append(_reject_decision(candidate, "invalid candidate timing"))
            continue
        start_time, end_time, trigger_time = candidate_timing
        unsupported = expression_type not in SUPPORTED_FINAL_EXPRESSIONS
        total_score = _total_score(rubric_scores)
        below_threshold = (
            rubric_scores["semantic_fit"] < 2
            or rubric_scores["type_specific"] < 2
            or total_score < MIN_TOTAL_SCORE_TO_KEEP
        )
        if unsupported or below_threshold:
            if unsupported:
                reason = "unsupported expression type"
            elif below_threshold:
                reason = "semantic/type rubric below keep threshold"
            else:
                reason = _clean_text(item.get("disqualifier")) or _clean_text(item.get("reason")) or "candidate rejected by rubric"
            rejected = _reject_decision(candidate, reason)
            rejected.update(
                {
                    "expression_type": expression_type if expression_type in SUPPORTED_FINAL_EXPRESSIONS else "",
                    "rubric_scores": rubric_scores,
                    "total_score": total_score,
                    "importance_score": _round_time(total_score / MAX_TOTAL_SCORE),
                    "start_time": _round_time(start_time),
                    "end_time": _round_time(end_time),
                    "trigger_time": _round_time(trigger_time),
                    "disqualifier": _clean_text(item.get("disqualifier")) or reason,
                    "summary": _clean_text(item.get("summary") or candidate.get("summary")),
                    "reason": reason,
                }
            )
            decisions.append(rejected)
            continue
        decisions.append(
            {
                "candidate_id": candidate_id,
                "source_branch": str(candidate.get("source_branch") or ""),
                "candidate_type": str(candidate.get("candidate_type") or ""),
                "decision": "keep",
                "expression_type": expression_type,
                "rubric_scores": rubric_scores,
                "total_score": total_score,
                "importance_score": _round_time(total_score / MAX_TOTAL_SCORE),
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "trigger_time": _round_time(trigger_time),
                "disqualifier": _clean_text(item.get("disqualifier")),
                "summary": _clean_text(item.get("summary") or candidate.get("summary")),
                "reason": _clean_text(item.get("reason")),
                "rank_reason": "",
            }
        )
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id and candidate_id not in seen:
            decisions.append(_reject_decision(candidate, "missing triggerability decision"))
    return decisions


def _decision_score(decision: dict[str, Any]) -> float:
    try:
        return float(decision.get("total_score", decision.get("importance_score", 0.0)))
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
                "rubric_scores": decision.get("rubric_scores") if isinstance(decision.get("rubric_scores"), dict) else {},
                "total_score": int(decision.get("total_score", 0) or 0),
                "importance_score": float(decision.get("importance_score", 0.0)),
                "disqualifier": str(decision.get("disqualifier") or ""),
                "summary": str(decision.get("summary") or ""),
                "reason": str(decision.get("reason") or ""),
            }
        )
    return final


__all__ = [
    "SUPPORTED_FINAL_EXPRESSIONS",
    "RUBRIC_SCORE_KEYS",
    "build_triggerability_prompt",
    "parse_triggerability_decisions",
    "select_top_expression_triggers",
]

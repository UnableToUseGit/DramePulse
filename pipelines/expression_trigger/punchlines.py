from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.candidates import _metadata_block


MAX_PUNCHLINE_SECONDS = 20.0


def build_punchline_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
) -> str:
    return "\n".join(
        [
            "## TASK",
            "You are a short-drama punchline annotator.",
            "Find comedic dialogue spans where one or several consecutive utterances create a joke, comeback, absurd wording, awkward reversal, or comic misunderstanding.",
            "Only output punchline candidates. Do not judge final player triggerability.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## RULES",
            "- A punchline candidate is a comedic dialogue span, not a plot segment or non-dialogue moment.",
            "- It may be one subtitle row or multiple consecutive subtitle rows when the comic effect needs the exchange.",
            "- Use `start_time` as the first utterance start time of the comedic dialogue span.",
            "- Use `end_time` as the last utterance end time of the comedic dialogue span.",
            "- `punchline_text` should quote the exact dialogue that creates the comic effect.",
            "- Reject ordinary plot payoff, ordinary cute tone, generic light atmosphere, and jokes that only work as plot payback.",
            "- Reject sincere family, tearful, comforting, farewell, reunion, or emotionally moving conversations even if there is contrast.",
            "- Do not label emotional contrast, restrained sadness, or a character's sincere denial as comedy unless there is a specific intentionally funny line.",
            "- Reject vague funny mood unless there are specific dialogue lines that create the comic effect.",
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `punchline_candidates`.",
            "Each candidate must contain exactly these keys: `start_time`, `end_time`, `summary`, `punchline_text`, `reason`, `evidence`.",
            json.dumps(
                {
                    "punchline_candidates": [
                        {
                            "start_time": 63.43,
                            "end_time": 64.75,
                            "summary": "女主用口水帮领导消毒形成笑点。",
                            "punchline_text": "来嘛，我帮你消毒！",
                            "reason": "女主把领导对毒素的夸张担心反制成荒诞消毒动作，形成喜剧反差。",
                            "evidence": ["63.430-64.750 来嘛，我帮你消毒！"],
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


def _iter_punchline_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("punchline_candidates"), list):
        return raw["punchline_candidates"]
    if isinstance(raw, list):
        return raw
    return []


def _evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def parse_punchline_candidates(raw: Any, *, video_id: str, duration_sec: float) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _iter_punchline_items(raw):
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if end_time - start_time > MAX_PUNCHLINE_SECONDS:
            continue
        if duration_sec > 0 and end_time > duration_sec:
            continue
        punchline_text = _clean_text(item.get("punchline_text") or item.get("punchline") or "")
        reason = _clean_text(item.get("reason") or item.get("payoff") or "")
        if not punchline_text or not reason:
            continue
        candidates.append(
            {
                "candidate_id": f"punchline_{video_id}_{len(candidates) + 1:03d}",
                "source_branch": "punchline",
                "candidate_type": "punchline",
                "expression_type": "笑点",
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "summary": _clean_text(item.get("summary") or ""),
                "punchline_text": punchline_text,
                "reason": reason,
                "evidence": _evidence_list(item.get("evidence")),
            }
        )
    return candidates


__all__ = [
    "MAX_PUNCHLINE_SECONDS",
    "build_punchline_prompt",
    "parse_punchline_candidates",
]

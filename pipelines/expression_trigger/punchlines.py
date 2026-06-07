from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.candidates import _metadata_block


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
            "You are the Punchline Branch of an expression-trigger pipeline.",
            "Find non-plot-structure comedy moments where viewers would naturally react with 笑点.",
            "Do not output plot payback, romance, tear, shock, or generic light tone.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## RULES",
            "- A punchline candidate must contain a setup and a clear punchline or comic reversal.",
            "- It can come from dialogue, dialect, exaggerated wording, awkward reversal, misunderstanding, or action plus dialogue.",
            "- Use `trigger_time` at the moment the joke becomes understandable.",
            "- Reject ordinary plot conflict, ordinary cute tone, and vague funny atmosphere.",
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `punchline_candidates`.",
            "Each candidate must contain exactly these keys: `start_time`, `end_time`, `trigger_time`, `summary`, `setup`, `punchline`, `payoff`, `evidence`.",
            json.dumps(
                {
                    "punchline_candidates": [
                        {
                            "start_time": 59.83,
                            "end_time": 68.15,
                            "trigger_time": 64.75,
                            "summary": "女主用口水帮领导消毒形成笑点。",
                            "setup": "领导夸张担心毒素进脑壳。",
                            "punchline": "来嘛，我帮你消毒！",
                            "payoff": "夸张担心和女主反制形成喜剧反差。",
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
            trigger_time = float(item["trigger_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if trigger_time < start_time or trigger_time > end_time:
            continue
        if duration_sec > 0 and end_time > duration_sec:
            continue
        punchline = _clean_text(item.get("punchline"))
        payoff = _clean_text(item.get("payoff"))
        if not punchline or not payoff:
            continue
        candidates.append(
            {
                "candidate_id": f"punchline_{video_id}_{len(candidates) + 1:03d}",
                "source_branch": "punchline",
                "candidate_type": "punchline",
                "expression_type": "笑点",
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "trigger_time": _round_time(trigger_time),
                "summary": _clean_text(item.get("summary")),
                "setup": _clean_text(item.get("setup")),
                "punchline": punchline,
                "payoff": payoff,
                "evidence": _evidence_list(item.get("evidence")),
            }
        )
    return candidates


__all__ = [
    "build_punchline_prompt",
    "parse_punchline_candidates",
]

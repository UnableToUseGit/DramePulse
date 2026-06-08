from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

INTERACTION_MODE = "inner_voice_danmaku"
DEFAULT_MAX_DURATION_SEC = 8.0
DEFAULT_MIN_DURATION_SEC = 5.0


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _episode_no(episode_id: str) -> int:
    match = re.search(r"(\d+)$", episode_id)
    if not match:
        raise ValueError(f"episode_id must end with a number: {episode_id}")
    return int(match.group(1))


def _candidate_peak_interval(candidate: dict[str, Any]) -> dict[str, Any] | None:
    cluster = candidate.get("cluster")
    if not isinstance(cluster, dict):
        return None
    peak_intervals = cluster.get("peakIntervals")
    if not isinstance(peak_intervals, list) or not peak_intervals:
        return None
    first = peak_intervals[0]
    return first if isinstance(first, dict) else None


def _duration_from_peak_interval(
    peak_interval: dict[str, Any],
    *,
    min_duration_sec: float,
    max_duration_sec: float,
) -> float | None:
    try:
        start_time = float(peak_interval["startTime"])
        end_time = float(peak_interval["endTime"])
    except (KeyError, TypeError, ValueError):
        return None
    if end_time <= start_time:
        return None
    return _round_time(max(min_duration_sec, min(max_duration_sec, end_time - start_time)))


def build_inner_voice_interaction_plan(
    selection_payload: dict[str, Any],
    *,
    series_id: str,
    episode_id: str,
    min_duration_sec: float = DEFAULT_MIN_DURATION_SEC,
    max_duration_sec: float = DEFAULT_MAX_DURATION_SEC,
) -> list[dict[str, Any]]:
    candidates = selection_payload.get("candidates")
    if not isinstance(candidates, list):
        return []
    episode_no = _episode_no(episode_id)
    plan: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        text = _clean_text(candidate.get("text"))
        if not text:
            continue
        peak_interval = _candidate_peak_interval(candidate)
        if peak_interval is None:
            continue
        try:
            trigger_time = float(peak_interval["startTime"])
        except (KeyError, TypeError, ValueError):
            continue
        duration_sec = _duration_from_peak_interval(
            peak_interval,
            min_duration_sec=min_duration_sec,
            max_duration_sec=max_duration_sec,
        )
        if duration_sec is None:
            continue
        video_id = _clean_text(candidate.get("videoId")) or _clean_text(selection_payload.get("videoId"))
        if not video_id:
            continue
        cluster = candidate.get("cluster") if isinstance(candidate.get("cluster"), dict) else {}
        interaction_id = f"ivp_{video_id}_{len(plan) + 1:03d}"
        plan.append(
            {
                "interaction_id": interaction_id,
                "video_id": video_id,
                "series_id": series_id,
                "episode_no": episode_no,
                "interaction_mode": INTERACTION_MODE,
                "trigger_time": _round_time(trigger_time),
                "duration_sec": duration_sec,
                "expire_time": _round_time(trigger_time + duration_sec),
                "content": {
                    "text": text,
                    "candidate_id": _clean_text(candidate.get("candidateId")),
                    "cluster_id": _clean_text(candidate.get("clusterId")),
                    "suitability_score": _round_time(float(candidate.get("suitabilityScore") or 0.0)),
                    "source_comment_ids": [str(value) for value in candidate.get("sourceCommentIds") or []],
                    "cluster_score_rank": cluster.get("scoreRank"),
                    "cluster_score": cluster.get("clusterScore"),
                    "cluster_comment_count": cluster.get("commentCount"),
                },
            }
        )
    return plan


def load_inner_voice_selection_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_interaction_plan_output(*, output_path: Path, plan: list[dict[str, Any]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "build_inner_voice_interaction_plan",
    "load_inner_voice_selection_payload",
    "write_interaction_plan_output",
]

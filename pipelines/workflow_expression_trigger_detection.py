from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any, Callable

from pipelines.client import LlmClientProtocol
from pipelines.expression_trigger_detection import (
    PLOT_PRIMARY_EXPRESSION_DEFINITIONS,
    SUPPORTED_PLOT_PRIMARY_EXPRESSIONS,
    _build_system_prompt,
    _clean_text,
    _round_time,
    filter_triggers_within_duration,
    format_expression_subtitle_timeline_seconds,
    normalize_plot_primary_expression,
    parse_expression_triggers,
)
from pipelines.utils import (
    SubtitleSegment,
    build_sample_timestamps,
    extract_frames_at_timestamps,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


@dataclass(frozen=True)
class WorkflowExpressionTriggerResult:
    expression_candidates: list[dict[str, Any]]
    candidate_decisions: list[dict[str, Any]]
    expression_triggers: list[dict[str, Any]]
    resonance_cues: list[dict[str, Any]]
    llm_calls: dict[str, dict[str, Any]]


ProgressCallback = Callable[[str, dict[str, Any]], None]


def _metadata_block(metadata: dict[str, Any] | None) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in (metadata or {}).items() if value is not None) or "- none"


def _expression_definitions_block() -> list[str]:
    expression_definitions = {label: description for label, description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS}
    return [
        "### 爽点",
        f"Definition: {expression_definitions['爽点']}",
        "Must-have: at this moment, the protagonist or justice side actively regains power, strikes back, wins a confrontation, exposes the truth, punishes the villain, or delivers a face-slapping reversal.",
        "Do not mislabel: simple escape from danger, being helped by someone else, being recognized, receiving an opportunity, or a generally positive turn without active counterattack is not a satisfying revenge/relief beat.",
        "",
        "### 甜点",
        f"Definition: {expression_definitions['甜点']}",
        "Must-have: after setup such as ambiguity, restraint, misunderstanding, protection, or mutual care, the relationship clearly warms up, gets confirmed, or moves forward intimately.",
        "Do not mislabel: ordinary help, polite interaction, teamwork, or protection without relationship advancement is not a romantic shipping beat.",
        "",
        "### 泪点",
        f"Definition: {expression_definitions['泪点']}",
        "Must-have: an emotional payoff such as sacrifice, reunion, farewell, selfless protection, forgiveness, or a family/love breakthrough makes viewers feel moved or tearful.",
        "Do not mislabel: mere hardship, pity, bullying, debt pressure, or ordinary sadness without emotional payoff is not a tearful/moving beat.",
        "",
        "### 笑点",
        f"Definition: {expression_definitions['笑点']}",
        "Must-have: a clear comedy beat formed by a punchline, physical gag, awkward reversal, exaggerated reaction, misunderstanding, or comic timing.",
        "Do not mislabel: ordinary light tone, generic cuteness, actor charm, or humor that only works through external fandom context is not a comedy beat.",
    ]


def _format_frame_timestamps(frame_timestamps_seconds: list[float]) -> str:
    return ", ".join(f"{timestamp:.3f}" for timestamp in frame_timestamps_seconds) if frame_timestamps_seconds else "none"


def _merge_time_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start_time, end_time in sorted(ranges):
        if not merged or start_time > merged[-1][1]:
            merged.append((start_time, end_time))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end_time))
    return merged


def _overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def build_visual_candidate_windows(
    *,
    subtitle_segments: list[SubtitleSegment],
    duration_sec: float,
    window_sec: float = 10.0,
    min_window_sec: float = 4.0,
    max_windows: int = 4,
) -> list[dict[str, Any]]:
    if duration_sec <= 0 or window_sec <= 0 or min_window_sec <= 0:
        return []
    ranges: list[tuple[float, float, str]] = []
    start = 0.0
    while start < duration_sec:
        end = min(duration_sec, start + window_sec)
        covered = sum(_overlap_seconds(start, end, segment.start, segment.end) for segment in subtitle_segments)
        coverage_ratio = covered / max(end - start, 0.001)
        if coverage_ratio <= 0.25 and end - start >= min_window_sec:
            ranges.append((_round_time(start), _round_time(end), "low_dialogue_density"))
        start = _round_time(end)

    windows: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()
    for start_time, end_time, reason in sorted(ranges, key=lambda item: (item[0], item[1], item[2])):
        key = (start_time, end_time, reason)
        if key in seen:
            continue
        seen.add(key)
        windows.append({"start_time": start_time, "end_time": end_time, "reason": reason})
        if len(windows) >= max_windows:
            break
    return windows


def build_visual_candidate_frame_timestamps(
    *,
    visual_candidate_windows: list[dict[str, Any]],
    duration_sec: float,
    interval_sec: float = 1.0,
    max_frames: int | None = 80,
) -> list[float]:
    if duration_sec <= 0 or not visual_candidate_windows:
        return []
    if interval_sec <= 0:
        raise ValueError("interval_sec must be positive")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive")

    timestamps: list[float] = []
    for window in visual_candidate_windows:
        try:
            start_time = max(0.0, float(window["start_time"]))
            end_time = min(duration_sec, float(window["end_time"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end_time <= start_time:
            continue
        current = _round_time(start_time)
        while current < end_time and current < duration_sec:
            timestamps.append(_round_time(current))
            current = round(current + interval_sec, 3)

    unique_timestamps = sorted(set(timestamps))
    if max_frames is not None and len(unique_timestamps) > max_frames:
        if max_frames == 1:
            return [unique_timestamps[0]]
        last_index = len(unique_timestamps) - 1
        selected_indexes = {
            round(index * last_index / float(max_frames - 1))
            for index in range(max_frames)
        }
        return [unique_timestamps[index] for index in sorted(selected_indexes)]
    return unique_timestamps


def _normalize_visual_candidate_window_ranges(
    *,
    visual_candidate_windows: list[dict[str, Any]],
    duration_sec: float,
) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for window in visual_candidate_windows:
        try:
            start_time = max(0.0, float(window["start_time"]))
            end_time = min(duration_sec, float(window["end_time"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end_time > start_time:
            ranges.append((_round_time(start_time), _round_time(end_time)))
    return ranges


def _is_timestamp_inside_window_ranges(timestamp: float, ranges: list[tuple[float, float]]) -> bool:
    return any(start_time <= timestamp < end_time for start_time, end_time in ranges)


def _resample_timestamps_by_index(timestamps: list[float], max_frames: int | None) -> list[float]:
    if max_frames is None or len(timestamps) <= max_frames:
        return timestamps
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")
    if max_frames == 1:
        return [timestamps[0]]
    last_index = len(timestamps) - 1
    selected_indexes = {
        round(index * last_index / float(max_frames - 1))
        for index in range(max_frames)
    }
    return [timestamps[index] for index in sorted(selected_indexes)]


def build_candidate_generation_frame_timestamps(
    *,
    duration_sec: float,
    sample_interval_sec: float,
    max_frames: int | None,
    visual_candidate_windows: list[dict[str, Any]],
    visual_window_sample_interval_sec: float = 1.0,
    visual_window_max_frames: int | None = 80,
) -> list[float]:
    window_ranges = _normalize_visual_candidate_window_ranges(
        visual_candidate_windows=visual_candidate_windows,
        duration_sec=duration_sec,
    )
    if not window_ranges:
        return build_sample_timestamps(
            duration_sec=duration_sec,
            sample_interval_sec=sample_interval_sec,
            max_frames=max_frames,
        )
    global_timestamps = build_sample_timestamps(
        duration_sec=duration_sec,
        sample_interval_sec=sample_interval_sec,
        max_frames=None,
    )
    global_timestamps = [
        timestamp
        for timestamp in global_timestamps
        if not _is_timestamp_inside_window_ranges(timestamp, window_ranges)
    ]
    global_timestamps = _resample_timestamps_by_index(global_timestamps, max_frames)
    visual_timestamps = build_visual_candidate_frame_timestamps(
        visual_candidate_windows=visual_candidate_windows,
        duration_sec=duration_sec,
        interval_sec=visual_window_sample_interval_sec,
        max_frames=visual_window_max_frames,
    )
    return sorted(set(global_timestamps + visual_timestamps))


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


def _format_visual_candidate_windows(windows: list[dict[str, Any]]) -> str:
    if not windows:
        return "none"
    return json.dumps(windows, ensure_ascii=False, separators=(",", ":"))


def _build_candidate_generation_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
    frame_timestamps_seconds: list[float],
    visual_candidate_windows: list[dict[str, Any]] | None = None,
) -> str:
    return "\n".join(
        [
            "## TASK",
            "Find candidate story intervals in a short-drama episode where viewers may naturally want to react immediately.",
            "The possible reaction types are: 爽点, 甜点, 泪点, 笑点.",
            "Use the full subtitle timeline as the main story context and use the sampled video frames as visual evidence.",
            "Also inspect low-dialogue visual windows because action, performance, intimacy, or combat payoff may happen with few or no subtitles.",
            "Prefer recall over precision: include plausible emotional beats, but avoid pure plot summaries with no viewer-reaction value.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            f"FRAME_TIMESTAMPS_SECONDS: {_format_frame_timestamps(frame_timestamps_seconds)}",
            "You will receive one sampled video frame for each timestamp listed above.",
            "You will also receive timestamped subtitle utterances for the full episode.",
            "All subtitle timestamps and output times are plain seconds, not MM:SS or HH:MM:SS.",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## SELECTION_RULES",
            "- A candidate is a short story interval that could make viewers want to send a bullet comment, tap an emotion button, or express an immediate reaction.",
            "- Do not select ordinary plot progression, background exposition, character introduction, simple conflict, simple danger, or simple suffering unless there is a clear viewer-reaction payoff.",
            "- Include enough setup and release context inside the interval; do not isolate a single line or a single frame when the emotion depends on surrounding context.",
            "- A candidate interval may be slightly wider than the actual emotional peak.",
            "- `primary_expression` must be exactly one value from `## PRIMARY_EXPRESSIONS`.",
            "- If subtitles alone support the judgment, use `subtitle` in `evidence_sources`; if video frames provide important evidence, also include `frame`.",
            "",
            "## PRIMARY_EXPRESSIONS",
            *_expression_definitions_block(),
            "",
            "## VISUAL_CANDIDATE_WINDOWS",
            _format_visual_candidate_windows(visual_candidate_windows or []),
            "These windows are fixed low-dialogue-density regions. They are not automatically highlights, but you must inspect frames around them for visual-only payoff such as combat reversal, hidden strength reveal, physical gag, kiss, hug, crying, or reaction shot.",
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `expression_candidates`.",
            "Each candidate object must contain exactly these keys: `start_time`, `end_time`, `primary_expression`, `summary`, `setup`, `turning_point`, `expression_release`, `candidate_reason`, `evidence_sources`.",
            "`setup`, `turning_point`, and `expression_release` are candidate-level hypotheses. The later review may correct or reject them.",
            "Output shape:",
            '{"expression_candidates":[{"start_time":48.0,"end_time":66.0,"primary_expression":"泪点","summary":"陈哥卖房凑钱给工人发工程款。","setup":"工人一直等不到钱，陈哥此前承受资金压力。","turning_point":"陈哥卖房筹钱，把钱发给工人。","expression_release":"前面的压力和承诺在这里兑现，可能让观众感动。","candidate_reason":"该片段具备善意兑现的情绪释放结构。","evidence_sources":["subtitle","frame"]}]}',
            "Field constraints:",
            "- `start_time` and `end_time` are numbers in seconds.",
            "- `start_time` must be >= 0.0.",
            "- `end_time` must be greater than `start_time` and <= VIDEO_DURATION_SECONDS.",
            "- `evidence_sources` is an array containing one or both of: `subtitle`, `frame`.",
            "- Use `frame` for visual-only candidates in low-dialogue windows, even if nearby subtitles are sparse.",
            "- Do not include any extra keys.",
            "",
            "## SUBTITLE_TIMELINE",
            subtitles_timeline,
        ]
    )


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


def _iter_candidate_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("expression_candidates"), list):
        return raw["expression_candidates"]
    if isinstance(raw, list):
        return raw
    return []


def parse_expression_trigger_candidates(
    raw: Any,
    *,
    video_id: str,
    duration_sec: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _iter_candidate_items(raw):
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if duration_sec > 0 and end_time > duration_sec:
            continue
        primary_expression = normalize_plot_primary_expression(item.get("primary_expression"))
        if primary_expression not in SUPPORTED_PLOT_PRIMARY_EXPRESSIONS:
            continue
        evidence_sources = item.get("evidence_sources")
        if not isinstance(evidence_sources, list):
            evidence_sources = []
        normalized_sources = [str(source) for source in evidence_sources if str(source) in {"subtitle", "frame"}]
        raw_candidate_id = item.get("candidate_id")
        candidate_id = _clean_text(raw_candidate_id) if raw_candidate_id is not None else ""
        candidates.append(
            {
                "candidate_id": candidate_id or f"cand_{video_id}_{len(candidates) + 1:03d}",
                "video_id": video_id,
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "primary_expression": primary_expression,
                "summary": _clean_text(item.get("summary")),
                "setup": _clean_text(item.get("setup") or ""),
                "turning_point": _clean_text(item.get("turning_point") or ""),
                "expression_release": _clean_text(item.get("expression_release") or ""),
                "candidate_reason": _clean_text(item.get("candidate_reason")),
                "evidence_sources": normalized_sources or ["subtitle"],
            }
        )
    return candidates


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
    for index, trigger in enumerate(sorted(triggers, key=lambda item: (_trigger_start_time(item), str(item.get("trigger_id", "")))), start=1):
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


def _trigger_quality_score(trigger: dict[str, Any]) -> float:
    try:
        intensity = float(trigger.get("intensity", 0.0))
    except (TypeError, ValueError):
        intensity = 0.0
    try:
        confidence = float(trigger.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return intensity * confidence


def _trigger_start_time(trigger: dict[str, Any]) -> float:
    try:
        return float(trigger["start_time"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def _trigger_end_time(trigger: dict[str, Any]) -> float:
    try:
        return float(trigger["end_time"])
    except (KeyError, TypeError, ValueError):
        return _trigger_start_time(trigger)


def consolidate_expression_triggers(
    triggers: list[dict[str, Any]],
    *,
    same_expression_gap_sec: float = 30.0,
    min_intensity: float = 0.6,
    min_confidence: float = 0.72,
    max_triggers: int | None = 4,
) -> list[dict[str, Any]]:
    if not triggers:
        return []

    filtered: list[dict[str, Any]] = []
    for trigger in triggers:
        try:
            intensity = float(trigger.get("intensity", 0.0))
            confidence = float(trigger.get("confidence", 0.0))
        except (TypeError, ValueError):
            continue
        if len(triggers) > 1 and (intensity < min_intensity or confidence < min_confidence):
            continue
        filtered.append(trigger)
    if not filtered:
        filtered = sorted(triggers, key=_trigger_quality_score, reverse=True)[:1]

    kept: list[dict[str, Any]] = []
    for trigger in sorted(filtered, key=lambda item: (_trigger_start_time(item), _trigger_end_time(item))):
        if not kept:
            kept.append(trigger)
            continue
        previous = kept[-1]
        same_expression = previous.get("primary_expression") == trigger.get("primary_expression")
        nearby = _trigger_start_time(trigger) - _trigger_end_time(previous) <= same_expression_gap_sec
        if same_expression and nearby:
            if _trigger_quality_score(trigger) > _trigger_quality_score(previous):
                kept[-1] = trigger
            continue
        kept.append(trigger)

    if max_triggers is not None and len(kept) > max_triggers:
        kept = sorted(kept, key=_trigger_quality_score, reverse=True)[:max_triggers]
    return sorted(kept, key=lambda item: (_trigger_start_time(item), str(item.get("trigger_id", ""))))


class WorkflowExpressionTriggerPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        sample_interval_sec: float = 10.0,
        max_frames: int | None = None,
        frame_max_height: int = 512,
        visual_candidate_window_sec: float = 10.0,
        visual_window_sample_interval_sec: float = 1.0,
        visual_window_max_frames: int | None = 80,
        filter_frame_interval_sec: float = 2.0,
        filter_candidate_context_sec: float = 2.0,
        filter_max_frames: int | None = 100,
        final_same_expression_gap_sec: float = 30.0,
        final_min_intensity: float = 0.6,
        final_min_confidence: float = 0.72,
        final_max_triggers: int | None = 4,
        candidate_max_output_tokens: int = 2400,
        filter_max_output_tokens: int = 2400,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames
        self.frame_max_height = frame_max_height
        self.visual_candidate_window_sec = visual_candidate_window_sec
        self.visual_window_sample_interval_sec = visual_window_sample_interval_sec
        self.visual_window_max_frames = visual_window_max_frames
        self.filter_frame_interval_sec = filter_frame_interval_sec
        self.filter_candidate_context_sec = filter_candidate_context_sec
        self.filter_max_frames = filter_max_frames
        self.final_same_expression_gap_sec = final_same_expression_gap_sec
        self.final_min_intensity = final_min_intensity
        self.final_min_confidence = final_min_confidence
        self.final_max_triggers = final_max_triggers
        self.candidate_max_output_tokens = candidate_max_output_tokens
        self.filter_max_output_tokens = filter_max_output_tokens
        self.progress_callback = progress_callback
        self.last_llm_call: dict[str, Any] = {}
        self.last_result: WorkflowExpressionTriggerResult | None = None

    def _emit_progress(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_callback is None:
            return
        self.progress_callback(event, payload)

    def _snapshot_llm_call(self) -> dict[str, Any]:
        diagnostics = getattr(self.llm_client, "last_call_diagnostics", {})
        return dict(diagnostics) if isinstance(diagnostics, dict) else {}

    def run(
        self,
        *,
        video_id: str,
        video_file_path: Path,
        subtitle_file_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowExpressionTriggerResult:
        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitle_duration = max((segment.end for segment in subtitle_segments), default=0.0)
        video_duration = probe_video_duration_seconds(video_file_path)
        duration_sec = max(subtitle_duration, video_duration or 0.0)
        visual_candidate_windows = build_visual_candidate_windows(
            subtitle_segments=subtitle_segments,
            duration_sec=duration_sec,
            window_sec=self.visual_candidate_window_sec,
        )
        timestamps = build_candidate_generation_frame_timestamps(
            duration_sec=duration_sec,
            sample_interval_sec=self.sample_interval_sec,
            max_frames=self.max_frames,
            visual_candidate_windows=visual_candidate_windows,
            visual_window_sample_interval_sec=self.visual_window_sample_interval_sec,
            visual_window_max_frames=self.visual_window_max_frames,
        )
        self._emit_progress(
            "prepared",
            {
                "video_id": video_id,
                "duration_sec": _round_time(duration_sec),
                "subtitle_segment_count": len(subtitle_segments),
                "visual_window_count": len(visual_candidate_windows),
                "visual_candidate_windows": visual_candidate_windows,
                "candidate_frame_count": len(timestamps),
                "sample_interval_sec": self.sample_interval_sec,
                "max_frames": self.max_frames,
                "visual_candidate_window_sec": self.visual_candidate_window_sec,
                "visual_window_sample_interval_sec": self.visual_window_sample_interval_sec,
                "visual_window_max_frames": self.visual_window_max_frames,
            },
        )
        subtitles_timeline = format_expression_subtitle_timeline_seconds(subtitle_segments)
        candidate_llm_call: dict[str, Any] = {}
        filter_llm_call: dict[str, Any] = {}
        candidate_decisions: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix=f"workflow_expression_{video_id}_") as temp_dir:
            output_dir = Path(temp_dir) / "frames"
            try:
                extraction = extract_frames_at_timestamps(
                    video_path=video_file_path,
                    output_dir=output_dir,
                    timestamps_seconds=timestamps,
                    max_height=self.frame_max_height,
                )
                image_paths = sorted(output_dir.glob("*.png")) if extraction.frame_count > 0 else []
                self._emit_progress(
                    "candidate_frames_extracted",
                    {
                        "video_id": video_id,
                        "requested_frame_count": len(timestamps),
                        "extracted_frame_count": extraction.frame_count,
                        "image_count": len(image_paths),
                        "frame_max_height": self.frame_max_height,
                    },
                )
            except Exception as exc:
                image_paths = []
                self._emit_progress(
                    "candidate_frames_extracted",
                    {
                        "video_id": video_id,
                        "requested_frame_count": len(timestamps),
                        "extracted_frame_count": 0,
                        "image_count": 0,
                        "frame_max_height": self.frame_max_height,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )

            self._emit_progress(
                "candidate_generation_start",
                {
                    "video_id": video_id,
                    "frame_count": len(timestamps),
                    "image_count": len(image_paths),
                    "max_tokens": self.candidate_max_output_tokens,
                },
            )
            try:
                raw_candidates = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=_build_candidate_generation_prompt(
                        video_id=video_id,
                        video_duration_seconds=duration_sec,
                        subtitles_timeline=subtitles_timeline,
                        metadata=metadata,
                        frame_timestamps_seconds=timestamps,
                        visual_candidate_windows=visual_candidate_windows,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=timestamps,
                    max_tokens=self.candidate_max_output_tokens,
                )
            finally:
                candidate_llm_call = self._snapshot_llm_call()
                self.last_llm_call = {
                    "candidate_generation": candidate_llm_call,
                    "candidate_filtering": filter_llm_call,
                }

            candidates = parse_expression_trigger_candidates(raw_candidates, video_id=video_id, duration_sec=duration_sec)
            self._emit_progress(
                "candidate_generation_done",
                {
                    "video_id": video_id,
                    "candidate_count": len(candidates),
                    "llm_status": candidate_llm_call.get("status"),
                    "elapsed_sec": candidate_llm_call.get("elapsed_sec"),
                    "total_tokens": (candidate_llm_call.get("usage") or {}).get("total_tokens")
                    if isinstance(candidate_llm_call.get("usage"), dict)
                    else None,
                },
            )
            if candidates:
                filter_timestamps = build_filter_frame_timestamps(
                    candidates=candidates,
                    duration_sec=duration_sec,
                    interval_sec=self.filter_frame_interval_sec,
                    context_sec=self.filter_candidate_context_sec,
                    max_frames=self.filter_max_frames,
                )
                filter_output_dir = Path(temp_dir) / "filter_frames"
                try:
                    filter_extraction = extract_frames_at_timestamps(
                        video_path=video_file_path,
                        output_dir=filter_output_dir,
                        timestamps_seconds=filter_timestamps,
                        max_height=self.frame_max_height,
                    )
                    filter_image_paths = sorted(filter_output_dir.glob("*.png")) if filter_extraction.frame_count > 0 else []
                    self._emit_progress(
                        "filter_frames_extracted",
                        {
                            "video_id": video_id,
                            "filter_frame_count": len(filter_timestamps),
                            "extracted_frame_count": filter_extraction.frame_count,
                            "image_count": len(filter_image_paths),
                            "frame_max_height": self.frame_max_height,
                        },
                    )
                except Exception as exc:
                    filter_image_paths = []
                    self._emit_progress(
                        "filter_frames_extracted",
                        {
                            "video_id": video_id,
                            "filter_frame_count": len(filter_timestamps),
                            "extracted_frame_count": 0,
                            "image_count": 0,
                            "frame_max_height": self.frame_max_height,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )

                self._emit_progress(
                    "candidate_filtering_start",
                    {
                        "video_id": video_id,
                        "candidate_count": len(candidates),
                        "frame_count": len(filter_timestamps),
                        "image_count": len(filter_image_paths),
                        "max_tokens": self.filter_max_output_tokens,
                    },
                )
                try:
                    raw_triggers = self.llm_client.generate_json_multimodal(
                        system_prompt=_build_system_prompt(),
                        user_prompt=_build_candidate_filter_prompt(
                            video_id=video_id,
                            video_duration_seconds=duration_sec,
                            subtitles_timeline=subtitles_timeline,
                            metadata=metadata,
                            candidates=candidates,
                            frame_timestamps_seconds=filter_timestamps,
                        ),
                        image_paths=filter_image_paths,
                        frame_timestamps_seconds=filter_timestamps,
                        max_tokens=self.filter_max_output_tokens,
                    )
                finally:
                    filter_llm_call = self._snapshot_llm_call()
                    self.last_llm_call = {
                        "candidate_generation": candidate_llm_call,
                        "candidate_filtering": filter_llm_call,
                    }
                candidate_decisions = parse_candidate_decisions(raw_triggers, candidates=candidates)
                parsed_triggers = filter_triggers_within_duration(
                    parse_expression_triggers(raw_triggers, video_id=video_id),
                    duration_sec=duration_sec,
                )
                triggers = consolidate_expression_triggers(
                    parsed_triggers,
                    same_expression_gap_sec=self.final_same_expression_gap_sec,
                    min_intensity=self.final_min_intensity,
                    min_confidence=self.final_min_confidence,
                    max_triggers=self.final_max_triggers,
                )
                self._emit_progress(
                    "candidate_filtering_done",
                    {
                        "video_id": video_id,
                        "candidate_decision_count": len(candidate_decisions),
                        "parsed_trigger_count": len(parsed_triggers),
                        "trigger_count": len(triggers),
                        "llm_status": filter_llm_call.get("status"),
                        "elapsed_sec": filter_llm_call.get("elapsed_sec"),
                        "total_tokens": (filter_llm_call.get("usage") or {}).get("total_tokens")
                        if isinstance(filter_llm_call.get("usage"), dict)
                        else None,
                    },
                )
            else:
                triggers = []
                candidate_decisions = []

        self.last_llm_call = {
            "candidate_generation": candidate_llm_call,
            "candidate_filtering": filter_llm_call,
        }
        result = WorkflowExpressionTriggerResult(
            expression_candidates=candidates,
            candidate_decisions=candidate_decisions,
            expression_triggers=sorted(triggers, key=lambda trigger: (float(trigger["start_time"]), str(trigger["trigger_id"]))),
            resonance_cues=build_resonance_cues(triggers, duration_sec=duration_sec),
            llm_calls=self.last_llm_call,
        )
        self._emit_progress(
            "completed",
            {
                "video_id": video_id,
                "candidate_count": len(result.expression_candidates),
                "candidate_decision_count": len(result.candidate_decisions),
                "trigger_count": len(result.expression_triggers),
                "resonance_cue_count": len(result.resonance_cues),
            },
        )
        self.last_result = result
        return result

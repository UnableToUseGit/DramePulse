from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import (
    PLOT_PRIMARY_EXPRESSION_DEFINITIONS,
    SUPPORTED_PLOT_PRIMARY_EXPRESSIONS,
    _clean_text,
    _round_time,
    normalize_plot_primary_expression,
)
from pipelines.utils import SubtitleSegment, build_sample_timestamps


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
    sorted_segments = sorted(
        (segment for segment in subtitle_segments if segment.end > segment.start),
        key=lambda segment: (segment.start, segment.end),
    )
    segment_index = 0
    windows: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()
    start = 0.0
    while start < duration_sec:
        end = min(duration_sec, start + window_sec)
        while segment_index < len(sorted_segments) and sorted_segments[segment_index].end <= start:
            segment_index += 1
        covered = 0.0
        scan_index = segment_index
        while scan_index < len(sorted_segments) and sorted_segments[scan_index].start < end:
            segment = sorted_segments[scan_index]
            covered += _overlap_seconds(start, end, segment.start, segment.end)
            scan_index += 1
        coverage_ratio = covered / max(end - start, 0.001)
        if coverage_ratio <= 0.25 and end - start >= min_window_sec:
            start_time = _round_time(start)
            end_time = _round_time(end)
            reason = "low_dialogue_density"
            key = (start_time, end_time, reason)
            if key not in seen:
                seen.add(key)
                windows.append({"start_time": start_time, "end_time": end_time, "reason": reason})
                if len(windows) >= max_windows:
                    break
        if end >= duration_sec:
            break
        start = end
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

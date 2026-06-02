from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from pipelines.client import LlmClientProtocol
from pipelines.expression_trigger_detection import (
    PLOT_PRIMARY_EXPRESSION_DEFINITIONS,
    SUPPORTED_PLOT_PRIMARY_EXPRESSIONS,
    _build_system_prompt,
    _clean_text,
    _round_time,
    filter_triggers_within_duration,
    format_expression_subtitle_timeline_seconds,
    parse_expression_triggers,
)
from pipelines.utils import (
    build_sample_timestamps,
    extract_frames_at_timestamps,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


@dataclass(frozen=True)
class WorkflowExpressionTriggerResult:
    expression_candidates: list[dict[str, Any]]
    expression_triggers: list[dict[str, Any]]
    llm_calls: dict[str, dict[str, Any]]


def _metadata_block(metadata: dict[str, Any] | None) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in (metadata or {}).items() if value is not None) or "- none"


def _expression_definitions_block() -> list[str]:
    expression_definitions = {label: description for label, description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS}
    return [
        "### 爽到了",
        f"Definition: {expression_definitions['爽到了']}",
        "Must-have: at this moment, the protagonist or justice side actively regains power, strikes back, wins a confrontation, exposes the truth, punishes the villain, or delivers a face-slapping reversal.",
        "Do not mislabel: simple escape from danger, being helped by someone else, being recognized, receiving an opportunity, or a generally positive turn without active counterattack is not a satisfying revenge/relief beat.",
        "",
        "### 磕到了",
        f"Definition: {expression_definitions['磕到了']}",
        "Must-have: after setup such as ambiguity, restraint, misunderstanding, protection, or mutual care, the relationship clearly warms up, gets confirmed, or moves forward intimately.",
        "Do not mislabel: ordinary help, polite interaction, teamwork, or protection without relationship advancement is not a romantic shipping beat.",
        "",
        "### 看哭了",
        f"Definition: {expression_definitions['看哭了']}",
        "Must-have: an emotional payoff such as sacrifice, reunion, farewell, selfless protection, forgiveness, or a family/love breakthrough makes viewers feel moved or tearful.",
        "Do not mislabel: mere hardship, pity, bullying, debt pressure, or ordinary sadness without emotional payoff is not a tearful/moving beat.",
        "",
        "### 笑死",
        f"Definition: {expression_definitions['笑死']}",
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


def _build_candidate_generation_prompt(
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
            "Find candidate story intervals in a short-drama episode where viewers may naturally want to react immediately.",
            "The possible reaction types are: 爽到了, 磕到了, 看哭了, 笑死.",
            "Use the full subtitle timeline as the main story context and use the sampled video frames as visual evidence.",
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
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `expression_candidates`.",
            "Each candidate object must contain exactly these keys: `start_time`, `end_time`, `primary_expression`, `summary`, `setup`, `turning_point`, `expression_release`, `candidate_reason`, `evidence_sources`.",
            "`setup`, `turning_point`, and `expression_release` are candidate-level hypotheses. The later review may correct or reject them.",
            "Output shape:",
            '{"expression_candidates":[{"start_time":48.0,"end_time":66.0,"primary_expression":"看哭了","summary":"陈哥卖房凑钱给工人发工程款。","setup":"工人一直等不到工程款，陈哥此前承受资金压力。","turning_point":"陈哥卖房筹钱，把工程款发给工人。","expression_release":"前面的压力和承诺在这里兑现，可能让观众感动。","candidate_reason":"该片段具备善意兑现的情绪释放结构。","evidence_sources":["subtitle","frame"]}]}',
            "Field constraints:",
            "- `start_time` and `end_time` are numbers in seconds.",
            "- `start_time` must be >= 0.0.",
            "- `end_time` must be greater than `start_time` and <= VIDEO_DURATION_SECONDS.",
            "- `evidence_sources` is an array containing one or both of: `subtitle`, `frame`.",
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
            "- If kept, refine `start_time`, `end_time`, and `cue_time` to the short viewer-reaction window inside the candidate interval.",
            "- `cue_time` should be the best moment to surface an interaction after the reaction payoff becomes understandable; do not place it before the payoff lands.",
            "- If rejected, omit it from `expression_triggers`.",
            "- `primary_expression` must be exactly one of: 爽到了, 磕到了, 看哭了, 笑死.",
            "",
            "## PRIMARY_EXPRESSIONS",
            *_expression_definitions_block(),
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `expression_triggers`.",
            "For rejected candidates, output nothing.",
            "For kept candidates, each object must contain exactly these keys: `candidate_id`, `decision`, `start_time`, `end_time`, `cue_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `setup`, `turning_point`, `expression_release`, `reason`.",
            "Use this exact object template for every kept trigger, in this exact key order:",
            '{"candidate_id":"","decision":"keep","start_time":0.0,"end_time":0.0,"cue_time":0.0,"source_type":"plot","primary_expression":"爽到了","intensity":0.0,"confidence":0.0,"summary":"","setup":"","turning_point":"","expression_release":"","reason":""}',
            'A rejected example is represented by omitting that candidate from `expression_triggers`; do not output `"decision":"reject"` objects.',
            "Field constraints:",
            "- `source_type` must be `plot`.",
            "- `end_time` must be <= VIDEO_DURATION_SECONDS.",
            "- `cue_time` must be within [start_time, end_time].",
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
        primary_expression = _clean_text(item.get("primary_expression"))
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


class WorkflowExpressionTriggerPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        sample_interval_sec: float = 10.0,
        max_frames: int | None = None,
        frame_max_height: int = 512,
        filter_frame_interval_sec: float = 2.0,
        filter_candidate_context_sec: float = 2.0,
        filter_max_frames: int | None = 100,
        candidate_max_output_tokens: int = 2400,
        filter_max_output_tokens: int = 2400,
    ) -> None:
        self.llm_client = llm_client
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames
        self.frame_max_height = frame_max_height
        self.filter_frame_interval_sec = filter_frame_interval_sec
        self.filter_candidate_context_sec = filter_candidate_context_sec
        self.filter_max_frames = filter_max_frames
        self.candidate_max_output_tokens = candidate_max_output_tokens
        self.filter_max_output_tokens = filter_max_output_tokens
        self.last_llm_call: dict[str, Any] = {}
        self.last_result: WorkflowExpressionTriggerResult | None = None

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
        timestamps = build_sample_timestamps(
            duration_sec=duration_sec,
            sample_interval_sec=self.sample_interval_sec,
            frames_per_interval=1,
            max_frames=self.max_frames,
        )
        subtitles_timeline = format_expression_subtitle_timeline_seconds(subtitle_segments)
        candidate_llm_call: dict[str, Any] = {}
        filter_llm_call: dict[str, Any] = {}

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
            except Exception:
                image_paths = []

            try:
                raw_candidates = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=_build_candidate_generation_prompt(
                        video_id=video_id,
                        video_duration_seconds=duration_sec,
                        subtitles_timeline=subtitles_timeline,
                        metadata=metadata,
                        frame_timestamps_seconds=timestamps,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=timestamps,
                    max_tokens=self.candidate_max_output_tokens,
                )
            finally:
                candidate_llm_call = self._snapshot_llm_call()

            candidates = parse_expression_trigger_candidates(raw_candidates, video_id=video_id, duration_sec=duration_sec)
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
                except Exception:
                    filter_image_paths = []

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
                triggers = filter_triggers_within_duration(
                    parse_expression_triggers(raw_triggers, video_id=video_id),
                    duration_sec=duration_sec,
                )
            else:
                triggers = []

        self.last_llm_call = {
            "candidate_generation": candidate_llm_call,
            "candidate_filtering": filter_llm_call,
        }
        result = WorkflowExpressionTriggerResult(
            expression_candidates=candidates,
            expression_triggers=sorted(triggers, key=lambda trigger: (float(trigger["start_time"]), str(trigger["trigger_id"]))),
            llm_calls=self.last_llm_call,
        )
        self.last_result = result
        return result

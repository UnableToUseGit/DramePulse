from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import time
from typing import Any, Callable

from pipelines.client import LlmClientProtocol
from pipelines.expression_trigger.baseline_mllm import (
    _build_system_prompt,
    _round_time,
)
from pipelines.expression_trigger.parsing import (
    filter_triggers_within_duration,
    format_expression_subtitle_timeline_seconds,
    parse_expression_triggers,
)
from pipelines.expression_trigger.candidates import (
    _build_candidate_generation_prompt,
    build_candidate_generation_frame_timestamps,
    build_visual_candidate_windows,
    normalize_mllm_frame_timestamps,
    parse_expression_trigger_candidates,
)
from pipelines.expression_trigger.postprocess import consolidate_expression_triggers
from pipelines.expression_trigger.resonance import build_resonance_cues
from pipelines.expression_trigger.review import (
    _build_candidate_filter_prompt,
    build_filter_frame_timestamps,
    parse_candidate_decisions,
)
from pipelines.common import (
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
        self._emit_progress(
            "preprocess_subtitles_loaded",
            {
                "video_id": video_id,
                "subtitle_segment_count": len(subtitle_segments),
                "subtitle_duration_sec": _round_time(subtitle_duration),
                "subtitle_file_path": str(subtitle_file_path),
            },
        )
        video_duration = probe_video_duration_seconds(video_file_path)
        duration_sec = max(subtitle_duration, video_duration or 0.0)
        self._emit_progress(
            "preprocess_duration_probed",
            {
                "video_id": video_id,
                "subtitle_duration_sec": _round_time(subtitle_duration),
                "video_duration_sec": _round_time(video_duration) if video_duration is not None else None,
                "duration_sec": _round_time(duration_sec),
                "video_file_path": str(video_file_path),
            },
        )
        self._emit_progress(
            "preprocess_visual_windows_start",
            {
                "video_id": video_id,
                "duration_sec": _round_time(duration_sec),
                "subtitle_segment_count": len(subtitle_segments),
                "visual_candidate_window_sec": self.visual_candidate_window_sec,
            },
        )
        visual_window_started_at = time.perf_counter()
        visual_candidate_windows = build_visual_candidate_windows(
            subtitle_segments=subtitle_segments,
            duration_sec=duration_sec,
            window_sec=self.visual_candidate_window_sec,
        )
        self._emit_progress(
            "preprocess_visual_windows_done",
            {
                "video_id": video_id,
                "visual_window_count": len(visual_candidate_windows),
                "elapsed_sec": round(time.perf_counter() - visual_window_started_at, 3),
            },
        )
        timestamps = normalize_mllm_frame_timestamps(
            build_candidate_generation_frame_timestamps(
                duration_sec=duration_sec,
                sample_interval_sec=self.sample_interval_sec,
                max_frames=self.max_frames,
                visual_candidate_windows=visual_candidate_windows,
                visual_window_sample_interval_sec=self.visual_window_sample_interval_sec,
                visual_window_max_frames=self.visual_window_max_frames,
            )
        )
        self._emit_progress(
            "preprocess_candidate_frames_built",
            {
                "video_id": video_id,
                "candidate_frame_count": len(timestamps),
                "sample_interval_sec": self.sample_interval_sec,
                "max_frames": self.max_frames,
                "visual_window_sample_interval_sec": self.visual_window_sample_interval_sec,
                "visual_window_max_frames": self.visual_window_max_frames,
            },
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

            candidates = parse_expression_trigger_candidates(
                raw_candidates,
                video_id=video_id,
                duration_sec=duration_sec,
                visual_candidate_windows=visual_candidate_windows,
            )
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
                filter_timestamps = normalize_mllm_frame_timestamps(
                    build_filter_frame_timestamps(
                        candidates=candidates,
                        duration_sec=duration_sec,
                        interval_sec=self.filter_frame_interval_sec,
                        context_sec=self.filter_candidate_context_sec,
                        max_frames=self.filter_max_frames,
                    )
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

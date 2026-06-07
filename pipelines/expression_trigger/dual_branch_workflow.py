from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import time
from typing import Any, Callable

from pipelines.client import LlmClientProtocol
from pipelines.expression_trigger.baseline_mllm import _build_system_prompt, _round_time
from pipelines.expression_trigger.parsing import format_expression_subtitle_timeline_seconds
from pipelines.expression_trigger.plot_beats import build_plot_beat_prompt, parse_plot_beat_candidates
from pipelines.expression_trigger.punchlines import build_punchline_prompt, parse_punchline_candidates
from pipelines.expression_trigger.triggerability import (
    build_triggerability_prompt,
    parse_triggerability_decisions,
    select_top_expression_triggers,
)
from pipelines.utils import (
    build_sample_timestamps,
    extract_frames_at_timestamps,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


@dataclass(frozen=True)
class DualBranchExpressionTriggerResult:
    plot_candidates: list[dict[str, Any]]
    punchline_candidates: list[dict[str, Any]]
    expression_candidates: list[dict[str, Any]]
    triggerability_decisions: list[dict[str, Any]]
    candidate_decisions: list[dict[str, Any]]
    expression_triggers: list[dict[str, Any]]
    resonance_cues: list[dict[str, Any]]
    llm_calls: dict[str, dict[str, Any]]


ProgressCallback = Callable[[str, dict[str, Any]], None]


class DualBranchExpressionTriggerPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        sample_interval_sec: float = 10.0,
        max_frames: int | None = None,
        frame_max_height: int = 512,
        top_k: int = 4,
        min_gap_seconds: float = 20.0,
        branch_max_output_tokens: int = 2400,
        judge_max_output_tokens: int = 2400,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames
        self.frame_max_height = frame_max_height
        self.top_k = top_k
        self.min_gap_seconds = min_gap_seconds
        self.branch_max_output_tokens = branch_max_output_tokens
        self.judge_max_output_tokens = judge_max_output_tokens
        self.progress_callback = progress_callback
        self.last_llm_call: dict[str, Any] = {}
        self.last_result: DualBranchExpressionTriggerResult | None = None

    def _emit_progress(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_callback is not None:
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
    ) -> DualBranchExpressionTriggerResult:
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
        timestamps = build_sample_timestamps(
            duration_sec=duration_sec,
            sample_interval_sec=self.sample_interval_sec,
            max_frames=self.max_frames,
        )
        self._emit_progress(
            "prepared",
            {
                "video_id": video_id,
                "duration_sec": _round_time(duration_sec),
                "subtitle_segment_count": len(subtitle_segments),
                "candidate_frame_count": len(timestamps),
                "sample_interval_sec": self.sample_interval_sec,
                "max_frames": self.max_frames,
            },
        )

        subtitles_timeline = format_expression_subtitle_timeline_seconds(subtitle_segments)
        plot_llm_call: dict[str, Any] = {}
        punchline_llm_call: dict[str, Any] = {}
        triggerability_llm_call: dict[str, Any] = {}

        with tempfile.TemporaryDirectory(prefix=f"dual_branch_expression_{video_id}_") as temp_dir:
            frame_output_dir = Path(temp_dir) / "plot_frames"
            try:
                extraction = extract_frames_at_timestamps(
                    video_path=video_file_path,
                    output_dir=frame_output_dir,
                    timestamps_seconds=timestamps,
                    max_height=self.frame_max_height,
                )
                image_paths = sorted(frame_output_dir.glob("*.png")) if extraction.frame_count > 0 else []
                self._emit_progress(
                    "plot_frames_extracted",
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
                    "plot_frames_extracted",
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
                "plot_branch_start",
                {
                    "video_id": video_id,
                    "frame_count": len(timestamps),
                    "image_count": len(image_paths),
                    "max_tokens": self.branch_max_output_tokens,
                },
            )
            plot_started_at = time.perf_counter()
            try:
                raw_plot_candidates = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=build_plot_beat_prompt(
                        video_id=video_id,
                        video_duration_seconds=duration_sec,
                        subtitles_timeline=subtitles_timeline,
                        metadata=metadata,
                        frame_timestamps_seconds=timestamps,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=timestamps,
                    max_tokens=self.branch_max_output_tokens,
                )
            finally:
                plot_llm_call = self._snapshot_llm_call()
                self.last_llm_call = {
                    "plot_branch": plot_llm_call,
                    "punchline_branch": punchline_llm_call,
                    "triggerability": triggerability_llm_call,
                }
            plot_candidates = parse_plot_beat_candidates(raw_plot_candidates, video_id=video_id, duration_sec=duration_sec)
            self._emit_progress(
                "plot_branch_done",
                {
                    "video_id": video_id,
                    "candidate_count": len(plot_candidates),
                    "elapsed_sec": round(time.perf_counter() - plot_started_at, 3),
                },
            )

            self._emit_progress(
                "punchline_branch_start",
                {"video_id": video_id, "max_tokens": self.branch_max_output_tokens},
            )
            punchline_started_at = time.perf_counter()
            try:
                raw_punchline_candidates = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=build_punchline_prompt(
                        video_id=video_id,
                        video_duration_seconds=duration_sec,
                        subtitles_timeline=subtitles_timeline,
                        metadata=metadata,
                    ),
                    image_paths=[],
                    frame_timestamps_seconds=[],
                    max_tokens=self.branch_max_output_tokens,
                )
            finally:
                punchline_llm_call = self._snapshot_llm_call()
                self.last_llm_call = {
                    "plot_branch": plot_llm_call,
                    "punchline_branch": punchline_llm_call,
                    "triggerability": triggerability_llm_call,
                }
            punchline_candidates = parse_punchline_candidates(raw_punchline_candidates, video_id=video_id, duration_sec=duration_sec)
            self._emit_progress(
                "punchline_branch_done",
                {
                    "video_id": video_id,
                    "candidate_count": len(punchline_candidates),
                    "elapsed_sec": round(time.perf_counter() - punchline_started_at, 3),
                },
            )

            expression_candidates = sorted(
                [*plot_candidates, *punchline_candidates],
                key=lambda item: (float(item["start_time"]), str(item.get("candidate_id", ""))),
            )
            self._emit_progress(
                "triggerability_start",
                {
                    "video_id": video_id,
                    "candidate_count": len(expression_candidates),
                    "top_k": self.top_k,
                    "min_gap_seconds": self.min_gap_seconds,
                    "max_tokens": self.judge_max_output_tokens,
                },
            )
            triggerability_started_at = time.perf_counter()
            try:
                raw_triggerability = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=build_triggerability_prompt(
                        video_id=video_id,
                        video_duration_seconds=duration_sec,
                        subtitles_timeline=subtitles_timeline,
                        candidates=expression_candidates,
                        top_k=self.top_k,
                        min_gap_seconds=self.min_gap_seconds,
                    ),
                    image_paths=[],
                    frame_timestamps_seconds=[],
                    max_tokens=self.judge_max_output_tokens,
                )
            finally:
                triggerability_llm_call = self._snapshot_llm_call()
                self.last_llm_call = {
                    "plot_branch": plot_llm_call,
                    "punchline_branch": punchline_llm_call,
                    "triggerability": triggerability_llm_call,
                }
            triggerability_decisions = parse_triggerability_decisions(raw_triggerability, candidates=expression_candidates)
            triggers = select_top_expression_triggers(
                triggerability_decisions,
                video_id=video_id,
                top_k=self.top_k,
                min_gap_seconds=self.min_gap_seconds,
            )
            self._emit_progress(
                "triggerability_done",
                {
                    "video_id": video_id,
                    "candidate_decision_count": len(triggerability_decisions),
                    "trigger_count": len(triggers),
                    "elapsed_sec": round(time.perf_counter() - triggerability_started_at, 3),
                },
            )

        self.last_llm_call = {
            "plot_branch": plot_llm_call,
            "punchline_branch": punchline_llm_call,
            "triggerability": triggerability_llm_call,
        }
        result = DualBranchExpressionTriggerResult(
            plot_candidates=plot_candidates,
            punchline_candidates=punchline_candidates,
            expression_candidates=expression_candidates,
            triggerability_decisions=triggerability_decisions,
            candidate_decisions=triggerability_decisions,
            expression_triggers=triggers,
            resonance_cues=[],
            llm_calls=self.last_llm_call,
        )
        self._emit_progress(
            "completed",
            {
                "video_id": video_id,
                "plot_candidate_count": len(result.plot_candidates),
                "punchline_candidate_count": len(result.punchline_candidates),
                "candidate_count": len(result.expression_candidates),
                "candidate_decision_count": len(result.candidate_decisions),
                "trigger_count": len(result.expression_triggers),
                "resonance_cue_count": len(result.resonance_cues),
            },
        )
        self.last_result = result
        return result


__all__ = [
    "DualBranchExpressionTriggerPipeline",
    "DualBranchExpressionTriggerResult",
]

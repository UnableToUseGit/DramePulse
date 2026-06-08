from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.triggerability import parse_triggerability_decisions, select_top_expression_triggers
from pipelines.utils import load_subtitle_segments


class PlotBeatTriggerabilityLlmClientProtocol(Protocol):
    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 2400,
    ) -> dict[str, Any]:
        ...


ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class PlotBeatTriggerabilityPipelineResult:
    video_id: str
    series_id: str
    created_at: str
    plot_candidates: list[dict[str, Any]]
    triggerability_decisions: list[dict[str, Any]]
    expression_triggers: list[dict[str, Any]]
    llm_calls: dict[str, dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_subtitles_timeline_one_decimal(subtitle_segments: list[Any]) -> str:
    lines = ["[SUBTITLE_TIMELINE]"]
    for segment in subtitle_segments:
        lines.append(f"[{float(segment.start):.1f}-{float(segment.end):.1f}] {segment.text}")
    lines.append("[/SUBTITLE_TIMELINE]")
    return "\n".join(lines)


def build_plot_beat_triggerability_system_prompt() -> str:
    return (
        "You are a raw plot beat selector for short-drama player interactions. "
        "Judge which already-detected plot beats are suitable player expression triggers. "
        "Return JSON only."
    )


def build_plot_beat_triggerability_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    plot_candidates: list[dict[str, Any]],
    top_k: int,
    min_gap_seconds: float,
) -> str:
    candidates_json = json.dumps({"plot_candidates": plot_candidates}, ensure_ascii=False, separators=(",", ":"))
    return "\n".join(
        [
            "## TASK",
            "You are selecting final player expression trigger moments from raw plot beat candidates.",
            "The raw plot beats may be dense and recall-oriented. Score every candidate with a fixed rubric.",
            "Do not decide keep/reject and do not rank or perform top-k selection. Downstream code will do that deterministically.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.1f}",
            "",
            "## FINAL_EXPRESSION_TYPES",
            "- 爽点: a hated antagonist, bully, oppressor, or unfair side first hurts/humiliates/suppresses the protagonist or sympathetic side, then gets counterattacked, exposed, face-slapped, punished, loses power, or publicly eats the loss.",
            "- 甜点: romantic or intimate payoff such as confession, kissing, couple-like care, mutual protection, relationship confirmation, or clear romantic warmth.",
            "- 泪点: accumulated family/love/sacrifice/guardianship/waiting/guilt/understanding emotion pays off through one concrete line or action.",
            "- 笑点: a clear comedic mechanism such as punchline, comic reveal, comic reversal, awkward misunderstanding, absurd wording/action, or sharp teasing.",
            "",
            "## JUDGING_RULES",
            "- Judge every candidate independently.",
            "- Do not perform top-k selection, do not enforce min_gap, and do not omit low-quality candidates.",
            "- If a candidate does not fit any final expression, set `expression_type` to `none` and use low rubric scores.",
            "- 爽点 requires a hated antagonist/oppressor and a payoff where that side is countered, defeated, embarrassed, or punished. Mere justice, benevolent repayment, a kind boss solving a debt, misunderstanding resolution, or things simply getting better is not 爽点.",
            "- 泪点 requires emotional accumulation and release; ordinary family logistics, casual care, or merely sending money home is not enough.",
            "- 笑点 requires a specific joke mechanism; do not treat sincere family or moving dialogue as comedy.",
            "- 甜点 is mainly romantic/intimate; ordinary friendship, family warmth, or generic relationship improvement is not enough.",
            "- Positive resolutions that do not fit any of the four expression types should be scored low instead of forcing a label.",
            "- Setup-only conflict starts and escalations without expression payoff should be scored low.",
            "- Ordinary plot logistics, exposition, repeated argument, and transitions should be scored low.",
            "- Unsupported shock-only or suspense-only beats should be scored low instead of forcing them into 笑点.",
            "- Do not output or adjust timing fields. Timing refinement is handled by a separate downstream step.",
            "",
            "## RUBRIC_SCORES",
            "Each score must be an integer 0, 1, or 2.",
            "- semantic_fit: 0=no valid final expression, 1=partial/ambiguous fit, 2=precise fit.",
            "- emotional_release: 0=setup/transition/logistics only, 1=some emotional value, 2=clear release/payoff.",
            "- viewer_impulse: 0=viewer unlikely to tap, 1=moderate impulse, 2=strong immediate impulse.",
            "- type_specific: 0=misses the core mechanism, 1=weak mechanism, 2=strong mechanism for the chosen type.",
            "",
            "## RAW_PLOT_BEAT_CANDIDATES",
            candidates_json,
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `triggerability_decisions`.",
            "Each decision must contain exactly these keys: `candidate_id`, `expression_type`, `rubric_scores`, `disqualifier`, `reason`.",
            json.dumps(
                {
                    "triggerability_decisions": [
                        {
                            "candidate_id": "pb_ch_demo_ep01_001_001",
                            "expression_type": "爽点",
                            "rubric_scores": {
                                "semantic_fit": 2,
                                "emotional_release": 2,
                                "viewer_impulse": 2,
                                "type_specific": 2,
                            },
                            "disqualifier": "",
                            "reason": "反击完成，观众可以表达解气。",
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


def _load_plot_beat_payload(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("plot_beats_path must contain a JSON object")
    if not isinstance(raw.get("chapter_plot_beats"), list):
        raise ValueError("plot_beats_path must contain `chapter_plot_beats` list")
    return raw


def flatten_plot_beat_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for chapter in payload.get("chapter_plot_beats") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = _clean_text(chapter.get("chapter_id") or "")
        for beat in chapter.get("plot_beats") or []:
            if not isinstance(beat, dict):
                continue
            beat_id = _clean_text(beat.get("beat_id") or "")
            beat_type = _clean_text(beat.get("beat_type") or beat.get("candidate_type") or "")
            start_time = _safe_float(beat.get("start_time"))
            end_time = _safe_float(beat.get("end_time"))
            if not beat_id or start_time is None or end_time is None or end_time <= start_time:
                continue
            candidates.append(
                {
                    "candidate_id": beat_id,
                    "source_beat_id": beat_id,
                    "source_branch": "plot_beat",
                    "chapter_id": chapter_id,
                    "candidate_type": beat_type,
                    "start_time": _round_time(start_time),
                    "end_time": _round_time(end_time),
                    "summary": _clean_text(beat.get("summary") or ""),
                    "reason": _clean_text(beat.get("reason") or ""),
                }
            )
    return candidates


class PlotBeatTriggerabilityPipeline:
    def __init__(
        self,
        *,
        llm_client: PlotBeatTriggerabilityLlmClientProtocol,
        top_k: int = 4,
        min_gap_seconds: float = 30.0,
        max_output_tokens: int = 6000,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.top_k = top_k
        self.min_gap_seconds = min_gap_seconds
        self.max_output_tokens = max_output_tokens
        self.progress_callback = progress_callback
        self.last_llm_call: dict[str, dict[str, Any]] = {}

    def _emit_progress(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_callback is not None:
            self.progress_callback(event, payload)

    def _snapshot_llm_call(self) -> dict[str, Any]:
        diagnostics = getattr(self.llm_client, "last_call_diagnostics", {})
        return dict(diagnostics) if isinstance(diagnostics, dict) else {}

    def run(self, *, plot_beats_path: Path, subtitle_file_path: Path) -> PlotBeatTriggerabilityPipelineResult:
        payload = _load_plot_beat_payload(plot_beats_path)
        video_id = _clean_text(payload.get("video_id") or "")
        series_id = _clean_text(payload.get("series_id") or "")
        if not video_id:
            raise ValueError("plot beats payload missing video_id")
        if not series_id:
            raise ValueError("plot beats payload missing series_id")

        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitles_timeline = _format_subtitles_timeline_one_decimal(subtitle_segments)
        plot_candidates = flatten_plot_beat_candidates(payload)
        subtitle_duration_sec = max((float(segment.end) for segment in subtitle_segments), default=0.0)
        beat_duration_sec = max((float(candidate["end_time"]) for candidate in plot_candidates), default=0.0)
        duration_sec = max(subtitle_duration_sec, beat_duration_sec)
        created_at = _now_iso()

        self._emit_progress(
            "prepared",
            {
                "video_id": video_id,
                "series_id": series_id,
                "candidate_count": len(plot_candidates),
                "subtitle_segment_count": len(subtitle_segments),
                "duration_sec": _round_time(duration_sec),
            },
        )
        started_at = time.perf_counter()
        self._emit_progress(
            "triggerability_start",
            {
                "video_id": video_id,
                "candidate_count": len(plot_candidates),
                "top_k": self.top_k,
                "min_gap_seconds": self.min_gap_seconds,
                "max_tokens": self.max_output_tokens,
            },
        )
        raw_decisions = self.llm_client.generate_json_multimodal(
            system_prompt=build_plot_beat_triggerability_system_prompt(),
            user_prompt=build_plot_beat_triggerability_prompt(
                video_id=video_id,
                video_duration_seconds=duration_sec,
                subtitles_timeline=subtitles_timeline,
                plot_candidates=plot_candidates,
                top_k=self.top_k,
                min_gap_seconds=self.min_gap_seconds,
            ),
            image_paths=[],
            frame_timestamps_seconds=[],
            max_tokens=self.max_output_tokens,
        )
        llm_calls = {"triggerability": self._snapshot_llm_call()}
        llm_calls["triggerability"]["parsed_response"] = raw_decisions
        triggerability_decisions = parse_triggerability_decisions(raw_decisions, candidates=plot_candidates)
        expression_triggers = select_top_expression_triggers(
            triggerability_decisions,
            video_id=video_id,
            top_k=self.top_k,
            min_gap_seconds=self.min_gap_seconds,
        )
        self.last_llm_call = llm_calls
        usage = llm_calls["triggerability"].get("usage")
        self._emit_progress(
            "triggerability_done",
            {
                "video_id": video_id,
                "candidate_decision_count": len(triggerability_decisions),
                "trigger_count": len(expression_triggers),
                "elapsed_sec": round(time.perf_counter() - started_at, 3),
                "total_tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
            },
        )
        self._emit_progress(
            "completed",
            {
                "video_id": video_id,
                "candidate_count": len(plot_candidates),
                "candidate_decision_count": len(triggerability_decisions),
                "trigger_count": len(expression_triggers),
            },
        )
        return PlotBeatTriggerabilityPipelineResult(
            video_id=video_id,
            series_id=series_id,
            created_at=created_at,
            plot_candidates=plot_candidates,
            triggerability_decisions=triggerability_decisions,
            expression_triggers=expression_triggers,
            llm_calls=llm_calls,
        )


__all__ = [
    "PlotBeatTriggerabilityPipeline",
    "PlotBeatTriggerabilityPipelineResult",
    "build_plot_beat_triggerability_prompt",
    "build_plot_beat_triggerability_system_prompt",
    "flatten_plot_beat_candidates",
]

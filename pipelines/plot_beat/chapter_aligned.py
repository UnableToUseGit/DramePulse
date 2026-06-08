from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Protocol

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.plot_beats import plot_beat_type_definitions_block
from pipelines.common import (
    extract_frames_at_timestamps,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


class ChapterAlignedPlotBeatLlmClientProtocol(Protocol):
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
class ChapterAlignedPlotBeatPipelineResult:
    video_id: str
    series_id: str
    created_at: str
    chapter_plot_beats: list[dict[str, Any]]
    llm_calls: dict[str, dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metadata_block(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))


def _format_full_subtitles_timeline_one_decimal(subtitle_segments: list[Any]) -> str:
    lines = ["[SUBTITLE_TIMELINE]"]
    for segment in subtitle_segments:
        lines.append(f"[{float(segment.start):.1f}-{float(segment.end):.1f}] {segment.text}")
    lines.append("[/SUBTITLE_TIMELINE]")
    return "\n".join(lines)


def _load_story_chapter_payload(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("story_chapters_path must contain a JSON object")
    if not isinstance(raw.get("story_chapters"), list):
        raise ValueError("story_chapters_path must contain `story_chapters` list")
    return raw


def _valid_chapters(payload: dict[str, Any]) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    for item in payload.get("story_chapters") or []:
        if not isinstance(item, dict):
            continue
        chapter_id = _clean_text(item.get("chapter_id") or "")
        start_time = _safe_float(item.get("start_time"))
        end_time = _safe_float(item.get("end_time"))
        if not chapter_id or start_time is None or end_time is None or end_time <= start_time:
            continue
        chapters.append(
            {
                "chapter_id": chapter_id,
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "title": _clean_text(item.get("title") or ""),
                "summary": _clean_text(item.get("summary") or ""),
                "reason": _clean_text(item.get("reason") or ""),
            }
        )
    return chapters


def _select_evenly_by_index(values: list[float], max_count: int) -> list[float]:
    if len(values) <= max_count:
        return values
    if max_count <= 0:
        return []
    if max_count == 1:
        return [values[0]]
    last_index = len(values) - 1
    indexes = {round(index * last_index / float(max_count - 1)) for index in range(max_count)}
    return [values[index] for index in sorted(indexes)]


def build_chapter_frame_timestamps(
    *,
    chapter_start_time: float,
    chapter_end_time: float,
    interval_sec: float = 1.0,
    max_frames: int = 60,
) -> list[float]:
    if chapter_end_time <= chapter_start_time or interval_sec <= 0.0 or max_frames <= 0:
        return []
    timestamps: list[float] = []
    current = round(float(chapter_start_time), 1)
    end_time = float(chapter_end_time)
    while current < end_time:
        timestamps.append(round(current, 1))
        current = round(current + interval_sec, 1)
    return _select_evenly_by_index(sorted(set(timestamps)), max_frames)


def build_chapter_plot_beat_system_prompt() -> str:
    return (
        "You are a short-drama plot beat annotator. "
        "Identify atomic story-state changes inside one chapter. "
        "Return JSON only."
    )


def build_chapter_plot_beat_user_prompt(
    *,
    video_id: str,
    series_id: str,
    video_duration_seconds: float,
    full_subtitles_timeline: str,
    chapter: dict[str, Any],
) -> str:
    output_shape = {
        "video_id": video_id,
        "series_id": series_id,
        "created_at": "2026-06-07T00:00:00Z",
        "chapter_id": chapter.get("chapter_id", ""),
        "plot_beats": [
            {
                "beat_id": "pb_ch_demo_001_001",
                "beat_type": "reversal",
                "start_time": 49.09,
                "end_time": 60.41,
                "summary": "工头说明工程款拨下一半，并卖房凑齐工资。",
                "reason": "剧情从讨薪冲突转为工资有望结清，冲突状态发生变化。",
            }
        ],
    }
    return "\n".join(
        [
            "## TASK",
            "Find plot beats for exactly one story chapter.",
            "Use the full subtitle timeline for context, but 只输出当前 chapter 范围内的 plot beats.",
            "The attached frames come only from the current chapter.",
            "",
            "## DEFINITION",
            "A plot beat is an atomic story-state change carried by one shot or one/two adjacent subtitle lines.",
            "`start_time` and `end_time` are the evidence span that carries the beat, not a chapter or scene interval.",
            "Target 1-8 seconds. Use up to 15 seconds only when one long subtitle line or continuous shot carries the beat.",
            "Do not output a whole phone call, whole argument, whole scene, chapter summary, setup arc, or aftermath.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"SERIES_ID: {series_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "",
            "## CURRENT_CHAPTER",
            _metadata_block(chapter),
            "",
            "## BEAT_TYPES",
            plot_beat_type_definitions_block(),
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly these keys: `video_id`, `series_id`, `created_at`, `chapter_id`, `plot_beats`.",
            "Each plot beat must contain exactly these keys: `beat_id`, `beat_type`, `start_time`, `end_time`, `summary`, `reason`.",
            "The final parser will overwrite `beat_id`, `video_id`, `series_id`, `created_at`, and `chapter_id`; still return them in this shape.",
            json.dumps(output_shape, ensure_ascii=False, separators=(",", ":")),
            "",
            "## FULL_SUBTITLES",
            full_subtitles_timeline or "(no subtitles)",
        ]
    )


def _iter_plot_beat_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("plot_beats"), list):
        return raw["plot_beats"]
    if isinstance(raw, list):
        return raw
    return []


def parse_chapter_plot_beat_result(
    raw: Any,
    *,
    video_id: str,
    series_id: str,
    created_at: str,
    chapter_id: str,
    chapter_start_time: float,
    chapter_end_time: float,
) -> dict[str, Any]:
    plot_beats: list[dict[str, Any]] = []
    for item in _iter_plot_beat_items(raw):
        if not isinstance(item, dict):
            continue
        beat_type = _clean_text(item.get("beat_type") or item.get("candidate_type") or "")
        start_time = _safe_float(item.get("start_time"))
        end_time = _safe_float(item.get("end_time"))
        plot_beats.append(
            {
                "beat_id": f"pb_{chapter_id}_{len(plot_beats) + 1:03d}",
                "beat_type": beat_type,
                "start_time": _round_time(start_time if start_time is not None else 0.0),
                "end_time": _round_time(end_time if end_time is not None else 0.0),
                "summary": _clean_text(item.get("summary") or ""),
                "reason": _clean_text(item.get("reason") or ""),
            }
        )
    return {
        "video_id": video_id,
        "series_id": series_id,
        "created_at": created_at,
        "chapter_id": chapter_id,
        "plot_beats": plot_beats,
    }


class ChapterAlignedPlotBeatPipeline:
    def __init__(
        self,
        *,
        llm_client: ChapterAlignedPlotBeatLlmClientProtocol,
        frame_interval_sec: float = 1.0,
        max_chapter_frames: int = 60,
        frame_max_height: int = 512,
        max_output_tokens: int = 2400,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.frame_interval_sec = frame_interval_sec
        self.max_chapter_frames = max_chapter_frames
        self.frame_max_height = frame_max_height
        self.max_output_tokens = max_output_tokens
        self.progress_callback = progress_callback
        self.last_llm_call: dict[str, dict[str, Any]] = {}

    def _emit_progress(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_callback is not None:
            self.progress_callback(event, payload)

    def _snapshot_llm_call(self) -> dict[str, Any]:
        diagnostics = getattr(self.llm_client, "last_call_diagnostics", {})
        return dict(diagnostics) if isinstance(diagnostics, dict) else {}

    def run(
        self,
        *,
        video_file_path: Path,
        subtitle_file_path: Path,
        story_chapters_path: Path,
    ) -> ChapterAlignedPlotBeatPipelineResult:
        story_payload = _load_story_chapter_payload(story_chapters_path)
        video_id = _clean_text(story_payload.get("video_id") or "")
        series_id = _clean_text(story_payload.get("series_id") or "")
        if not video_id:
            raise ValueError("story_chapters payload missing video_id")
        if not series_id:
            raise ValueError("story_chapters payload missing series_id")

        chapters = _valid_chapters(story_payload)
        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitle_duration = max((segment.end for segment in subtitle_segments), default=0.0)
        video_duration = probe_video_duration_seconds(video_file_path)
        duration_sec = max(subtitle_duration, video_duration or 0.0)
        full_subtitles_timeline = _format_full_subtitles_timeline_one_decimal(subtitle_segments)
        created_at = _now_iso()
        chapter_results: list[dict[str, Any]] = []
        llm_calls: dict[str, dict[str, Any]] = {}

        self._emit_progress(
            "prepared",
            {
                "video_id": video_id,
                "series_id": series_id,
                "chapter_count": len(chapters),
                "subtitle_segment_count": len(subtitle_segments),
                "duration_sec": _round_time(duration_sec),
            },
        )

        with tempfile.TemporaryDirectory(prefix=f"chapter_plot_beat_{video_id}_") as temp_dir:
            temp_root = Path(temp_dir)
            for chapter_index, chapter in enumerate(chapters, start=1):
                chapter_id = str(chapter["chapter_id"])
                frame_timestamps = build_chapter_frame_timestamps(
                    chapter_start_time=float(chapter["start_time"]),
                    chapter_end_time=float(chapter["end_time"]),
                    interval_sec=self.frame_interval_sec,
                    max_frames=self.max_chapter_frames,
                )
                self._emit_progress(
                    "chapter_start",
                    {
                        "video_id": video_id,
                        "series_id": series_id,
                        "chapter_id": chapter_id,
                        "chapter_index": chapter_index,
                        "chapter_count": len(chapters),
                        "start_time": float(chapter["start_time"]),
                        "end_time": float(chapter["end_time"]),
                        "title": str(chapter.get("title") or ""),
                        "summary": str(chapter.get("summary") or ""),
                        "frame_count": len(frame_timestamps),
                    },
                )
                frame_dir = temp_root / chapter_id.replace("/", "_")
                try:
                    extraction = extract_frames_at_timestamps(
                        video_path=video_file_path,
                        output_dir=frame_dir,
                        timestamps_seconds=frame_timestamps,
                        max_height=self.frame_max_height,
                    )
                    image_paths = sorted(frame_dir.glob("*.png")) if extraction.frame_count > 0 else []
                except Exception as exc:
                    image_paths = []
                    self._emit_progress(
                        "chapter_frames_extracted",
                        {
                            "video_id": video_id,
                            "chapter_id": chapter_id,
                            "requested_frame_count": len(frame_timestamps),
                            "extracted_frame_count": 0,
                            "image_count": 0,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                else:
                    self._emit_progress(
                        "chapter_frames_extracted",
                        {
                            "video_id": video_id,
                            "chapter_id": chapter_id,
                            "requested_frame_count": len(frame_timestamps),
                            "extracted_frame_count": extraction.frame_count,
                            "image_count": len(image_paths),
                        },
                    )

                self._emit_progress(
                    "chapter_llm_start",
                    {
                        "video_id": video_id,
                        "chapter_id": chapter_id,
                        "frame_count": len(frame_timestamps),
                        "image_count": len(image_paths),
                        "max_tokens": self.max_output_tokens,
                    },
                )
                started_at = time.perf_counter()
                raw_result = self.llm_client.generate_json_multimodal(
                    system_prompt=build_chapter_plot_beat_system_prompt(),
                    user_prompt=build_chapter_plot_beat_user_prompt(
                        video_id=video_id,
                        series_id=series_id,
                        video_duration_seconds=duration_sec,
                        full_subtitles_timeline=full_subtitles_timeline,
                        chapter=chapter,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=frame_timestamps,
                    max_tokens=self.max_output_tokens,
                )
                llm_calls[chapter_id] = self._snapshot_llm_call()
                parsed_result = parse_chapter_plot_beat_result(
                    raw_result,
                    video_id=video_id,
                    series_id=series_id,
                    created_at=created_at,
                    chapter_id=chapter_id,
                    chapter_start_time=float(chapter["start_time"]),
                    chapter_end_time=float(chapter["end_time"]),
                )
                chapter_results.append(parsed_result)
                llm_call = llm_calls.get(chapter_id, {})
                usage = llm_call.get("usage") if isinstance(llm_call, dict) else None
                self._emit_progress(
                    "chapter_llm_done",
                    {
                        "video_id": video_id,
                        "chapter_id": chapter_id,
                        "beat_count": len(parsed_result.get("plot_beats", [])),
                        "elapsed_sec": round(time.perf_counter() - started_at, 3),
                        "total_tokens": usage.get("total_tokens") if isinstance(usage, dict) else llm_call.get("total_tokens") if isinstance(llm_call, dict) else None,
                    },
                )

        self.last_llm_call = llm_calls
        self._emit_progress(
            "completed",
            {
                "video_id": video_id,
                "series_id": series_id,
                "chapter_count": len(chapter_results),
                "beat_count": sum(len(item.get("plot_beats", [])) for item in chapter_results),
            },
        )
        return ChapterAlignedPlotBeatPipelineResult(
            video_id=video_id,
            series_id=series_id,
            created_at=created_at,
            chapter_plot_beats=chapter_results,
            llm_calls=llm_calls,
        )


__all__ = [
    "ChapterAlignedPlotBeatPipeline",
    "ChapterAlignedPlotBeatPipelineResult",
    "build_chapter_frame_timestamps",
    "build_chapter_plot_beat_system_prompt",
    "build_chapter_plot_beat_user_prompt",
    "parse_chapter_plot_beat_result",
]

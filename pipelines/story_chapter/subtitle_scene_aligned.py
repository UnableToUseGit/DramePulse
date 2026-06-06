from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Protocol, Sequence

from pipelines.story_chapter.baseline_text import Utterance, _round_time, load_scenes, load_utterances_from_transcription
from pipelines.utils import FrameExtractionResult, extract_frames_at_timestamps


class SubtitleSceneAlignedLlmClientProtocol(Protocol):
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


@dataclass(frozen=True)
class DraftChapter:
    start_time: float
    end_time: float
    title: str
    summary: str
    importance: float
    reason: str
    start_reason: str
    end_reason: str
    start_utterance_id: str | None = None
    end_utterance_id: str | None = None


@dataclass(frozen=True)
class VisualGap:
    gap_id: str
    start_time: float
    end_time: float
    previous_chapter_id: str | None
    next_chapter_id: str | None


ExtractFrames = Callable[..., FrameExtractionResult | dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_importance(value: Any) -> float:
    number = _safe_float(value)
    if number is None:
        return 0.5
    return max(0.0, min(1.0, number))


def _format_utterance_line(utterance: Utterance) -> str:
    speaker = f" speaker={utterance.speaker_id}" if utterance.speaker_id is not None else ""
    return f"{utterance.utterance_id} [{utterance.start_time:.3f}-{utterance.end_time:.3f}]{speaker}: {utterance.text}"


def build_draft_chapter_system_prompt() -> str:
    return (
        "You are a short-drama story editor. "
        "Split one episode into coherent macro story chapters using subtitles only. "
        "Return valid JSON only."
    )


def build_draft_chapter_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
) -> str:
    utterance_lines = "\n".join(_format_utterance_line(utterance) for utterance in utterances)
    return "\n".join(
        [
            "## TASK",
            "Read the full subtitle transcript and decide the semantic story chapters.",
            "Short dramas are dialogue-driven, so use story goal changes, conflict resolution, location/task changes, and new macro events.",
            "Do not split a single macro event into setup/result micro beats.",
            "",
            "For each chapter, choose the first and last subtitle utterance covered by that chapter.",
            "Use the first subtitle utterance's start time as `start_time`.",
            "Use the last subtitle utterance's end time as `end_time`.",
            "Do not invent approximate boundary times.",
            "",
            "## OUTPUT JSON",
            "Return exactly this shape:",
            '{"chapters":[{"start_utterance_id":"u_001","start_time":1.16,"start_reason":"这是讨薪事件的第一句有效台词。","end_utterance_id":"u_018","end_time":83.5,"end_reason":"这句台词完成讨薪事件并进入返乡安排。","title":"讨薪成功","summary":"工人讨薪并拿到工钱。","reason":"讨薪事件完成并进入下一段返乡安排。","importance":0.7}]}',
            "",
            "Rules:",
            "- chapters must cover all subtitle utterances in order.",
            "- Do not skip any utterance and do not overlap utterances.",
            "- start_time must be copied from the chosen starting subtitle's start time.",
            "- end_time must be copied from the chosen ending subtitle's end time.",
            "- start_utterance_id must be the utterance_id of the first subtitle in the chapter.",
            "- end_utterance_id must be the utterance_id of the last subtitle in the chapter.",
            "- start_reason must explain why the chosen first subtitle starts this chapter.",
            "- end_reason must explain why the chosen last subtitle ends this chapter.",
            "- start_time must be increasing.",
            "- end_time must be increasing.",
            "- Each chapter must include a reason explaining why this subtitle range is one coherent story chapter.",
            "- Use speaker ids to distinguish dialogue turns when helpful, but do not invent character names from speaker ids alone.",
            "- Use 3-5 chapters for a typical short episode unless the story strongly requires otherwise.",
            "- title should be short and useful for player navigation.",
            "- summary should describe the chapter subtitle range.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "",
            "## FULL_SUBTITLES",
            utterance_lines or "(no subtitles)",
        ]
    )


def parse_draft_chapters(raw: dict[str, Any]) -> tuple[list[DraftChapter], list[str]]:
    warnings: list[str] = []
    raw_chapters = raw.get("chapters") if isinstance(raw, dict) else None
    if not isinstance(raw_chapters, list):
        return [], ["LLM response does not contain a chapters array."]

    drafts: list[DraftChapter] = []
    previous_end = -1.0
    for index, item in enumerate(raw_chapters, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Chapter draft #{index} is not an object.")
            continue
        start_time = _safe_float(item.get("start_time"))
        end_time = _safe_float(item.get("end_time"))
        if start_time is None or start_time < 0:
            warnings.append(f"Chapter draft #{index} has invalid start_time.")
            continue
        if end_time is None or end_time <= 0:
            warnings.append(f"Chapter draft #{index} has invalid end_time.")
            continue
        if end_time <= start_time:
            warnings.append(f"Chapter draft #{index} has end_time <= start_time.")
            continue
        if end_time <= previous_end:
            warnings.append(f"Chapter draft #{index} end_time is not increasing.")
            continue
        previous_end = end_time
        start_utterance_id = item.get("start_utterance_id")
        end_utterance_id = item.get("end_utterance_id")
        start_reason = str(item.get("start_reason") or "").strip()
        end_reason = str(item.get("end_reason") or "").strip()
        drafts.append(
            DraftChapter(
                start_time=_round_time(start_time),
                end_time=_round_time(end_time),
                title=str(item.get("title") or f"章节 {len(drafts) + 1}").strip(),
                summary=str(item.get("summary") or "").strip(),
                importance=_clamp_importance(item.get("importance", 0.5)),
                reason=str(item.get("reason") or "").strip() or "LLM did not provide a reason.",
                start_reason=start_reason or "LLM did not provide a start reason.",
                end_reason=end_reason or "LLM did not provide an end reason.",
                start_utterance_id=str(start_utterance_id).strip() if start_utterance_id is not None else None,
                end_utterance_id=str(end_utterance_id).strip() if end_utterance_id is not None else None,
            )
        )
    return drafts, warnings


def _scene_start_containing_time(time_sec: float, scenes: Sequence[dict[str, Any]]) -> float | None:
    candidates: list[float] = []
    for scene in scenes:
        try:
            start_time = float(scene["start_time"])
            end_time = float(scene["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time <= time_sec < end_time or start_time < time_sec <= end_time:
            candidates.append(start_time)
    if not candidates:
        return None
    return _round_time(max(candidates))


def _scene_end_containing_time(time_sec: float, scenes: Sequence[dict[str, Any]]) -> float | None:
    candidates: list[float] = []
    for scene in scenes:
        try:
            start_time = float(scene["start_time"])
            end_time = float(scene["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < time_sec <= end_time or start_time <= time_sec < end_time:
            candidates.append(end_time)
    if not candidates:
        return None
    return _round_time(min(candidates))


def align_draft_chapters_to_scene_boundaries(
    *,
    video_id: str,
    video_duration_seconds: float,
    scenes: Sequence[dict[str, Any]],
    drafts: Sequence[DraftChapter],
    max_alignment_window_seconds: float = 10.0,
    min_chapter_seconds: float = 12.0,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not drafts:
        return [
            {
                "chapter_id": f"ch_{video_id}_001",
                "video_id": video_id,
                "start_time": 0.0,
                "end_time": _round_time(video_duration_seconds),
                "title": "全片",
                "summary": "",
                "reason": "No valid subtitle draft chapters were returned; generated one full-episode chapter.",
                "importance": 0.5,
                "alignment": {
                    "subtitle_start_time": 0.0,
                    "subtitle_end_time": _round_time(video_duration_seconds),
                    "aligned_scene_start_time": 0.0,
                    "aligned_scene_end_time": _round_time(video_duration_seconds),
                },
            }
        ], ["No valid subtitle draft chapters; generated one full-episode fallback chapter."]

    chapters: list[dict[str, Any]] = []
    for index, draft in enumerate(drafts, start=1):
        aligned_start = _scene_start_containing_time(draft.start_time, scenes)
        aligned_end = _scene_end_containing_time(draft.end_time, scenes)
        if aligned_start is None:
            warnings.append(f"Could not find containing scene for draft chapter #{index} start_time={draft.start_time:.3f}.")
            continue
        if aligned_end is None:
            warnings.append(f"Could not find containing scene for draft chapter #{index} end_time={draft.end_time:.3f}.")
            continue
        if aligned_end <= aligned_start:
            warnings.append(f"Aligned draft chapter #{index} has end_time <= start_time.")
            continue
        chapters.append(
            {
                "chapter_id": f"ch_{video_id}_{index:03d}",
                "video_id": video_id,
                "start_time": aligned_start,
                "end_time": aligned_end,
                "title": draft.title,
                "summary": draft.summary,
                "reason": draft.reason,
                "importance": draft.importance,
                "alignment": {
                    "start_utterance_id": draft.start_utterance_id,
                    "end_utterance_id": draft.end_utterance_id,
                    "start_reason": draft.start_reason,
                    "end_reason": draft.end_reason,
                    "subtitle_start_time": draft.start_time,
                    "subtitle_end_time": draft.end_time,
                    "aligned_scene_start_time": aligned_start,
                    "aligned_scene_end_time": aligned_end,
                    "start_alignment_error_seconds": _round_time(aligned_start - draft.start_time),
                    "end_alignment_error_seconds": _round_time(aligned_end - draft.end_time),
                },
            }
        )
    return chapters, warnings


def normalize_aligned_chapters(chapters: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    normalized = [dict(chapter) for chapter in sorted(chapters, key=lambda item: (float(item["start_time"]), float(item["end_time"])))]
    warnings: list[str] = []
    previous_end: float | None = None
    previous_id: str | None = None
    result: list[dict[str, Any]] = []
    for chapter in normalized:
        start_time = _round_time(float(chapter["start_time"]))
        end_time = _round_time(float(chapter["end_time"]))
        if previous_end is not None and start_time < previous_end:
            warnings.append(
                f"Resolved aligned subtitle chapter overlap: {previous_id} end_time={previous_end:.3f}, "
                f"{chapter['chapter_id']} start_time={start_time:.3f}."
            )
            start_time = previous_end
        if end_time <= start_time:
            warnings.append(f"Dropped zero-length aligned subtitle chapter {chapter['chapter_id']}.")
            continue
        chapter["start_time"] = start_time
        chapter["end_time"] = end_time
        result.append(chapter)
        previous_end = end_time
        previous_id = str(chapter["chapter_id"])
    return result, warnings


def find_visual_gaps(
    chapters: Sequence[dict[str, Any]],
    *,
    video_duration_seconds: float,
) -> list[VisualGap]:
    gaps: list[VisualGap] = []
    if not chapters:
        return [
            VisualGap(
                gap_id="gap_001",
                start_time=0.0,
                end_time=_round_time(video_duration_seconds),
                previous_chapter_id=None,
                next_chapter_id=None,
            )
        ]
    first = chapters[0]
    first_start = float(first["start_time"])
    if first_start > 0.0:
        gaps.append(
            VisualGap(
                gap_id=f"gap_{len(gaps) + 1:03d}",
                start_time=0.0,
                end_time=_round_time(first_start),
                previous_chapter_id=None,
                next_chapter_id=str(first["chapter_id"]),
            )
        )
    for previous, current in zip(chapters, chapters[1:]):
        previous_end = float(previous["end_time"])
        current_start = float(current["start_time"])
        if current_start <= previous_end:
            continue
        gaps.append(
            VisualGap(
                gap_id=f"gap_{len(gaps) + 1:03d}",
                start_time=_round_time(previous_end),
                end_time=_round_time(current_start),
                previous_chapter_id=str(previous["chapter_id"]),
                next_chapter_id=str(current["chapter_id"]),
            )
        )
    last = chapters[-1]
    last_end = float(last["end_time"])
    duration = _round_time(video_duration_seconds)
    if duration > last_end:
        gaps.append(
            VisualGap(
                gap_id=f"gap_{len(gaps) + 1:03d}",
                start_time=_round_time(last_end),
                end_time=duration,
                previous_chapter_id=str(last["chapter_id"]),
                next_chapter_id=None,
            )
        )
    return gaps


def _format_chapter_context(chapter: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"chapter_id: {chapter['chapter_id']}",
            f"time_range: {float(chapter['start_time']):.3f}-{float(chapter['end_time']):.3f}",
            f"title: {chapter['title']}",
            f"summary: {chapter['summary']}",
            f"reason: {chapter['reason']}",
        ]
    )


def build_gap_review_system_prompt() -> str:
    return (
        "You are a multimodal short-drama chapter gap reviewer. "
        "Classify every visual gap between two subtitle-based story chapters. "
        "Return valid JSON only."
    )


def build_gap_review_user_prompt(
    *,
    video_id: str,
    gaps: Sequence[VisualGap],
    chapters_by_id: dict[str, dict[str, Any]],
    frame_timestamps_by_gap: dict[str, list[float]],
) -> str:
    lines = [
        "## TASK",
        "For each visual gap between subtitle-based chapters, decide whether it belongs to the previous chapter, belongs to the next chapter, or is an independent visual chapter.",
        "Use the previous and next chapter summaries, their reasons, and the sampled video frames.",
        "",
        "Decision values:",
        "- merge_previous: the gap primarily completes the previous chapter, such as its reaction shot, emotional payoff, action aftermath, object/scene close-up, or outgoing transition.",
        "- merge_next: the gap primarily opens the next chapter, such as its location setup, character entrance, establishing shot, preparatory action, or incoming transition.",
        "- standalone: the gap has its own readable visual event, montage, travel/action sequence, time passage, or music-driven beat that a viewer would expect as a separate timeline chapter.",
        "If the gap is at the beginning of the video, choose merge_next or standalone.",
        "If the gap is at the end of the video, choose merge_previous or standalone.",
        "",
        "## OUTPUT JSON",
        "Return exactly this shape:",
        '{"gap_reviews":[{"gap_id":"gap_001","decision":"merge_previous","title":null,"summary":null,"reason":"这是上一章讨薪成功后的情绪收尾。"}]}',
        "Rules:",
        "- Return one review for every gap_id.",
        "- decision must be one of: merge_previous, merge_next, standalone.",
        "- reason is required for every review.",
        "- title and summary are required only when decision is standalone; otherwise use null.",
        "",
        f"## VIDEO_ID\n{video_id}",
        "",
        "## GAPS",
    ]
    for gap in gaps:
        previous = chapters_by_id.get(gap.previous_chapter_id or "")
        current = chapters_by_id.get(gap.next_chapter_id or "")
        frame_times = ", ".join(f"{timestamp:.3f}" for timestamp in frame_timestamps_by_gap.get(gap.gap_id, []))
        lines.extend(
            [
                f"GAP_ID: {gap.gap_id}",
                f"GAP_TIME_RANGE: {gap.start_time:.3f}-{gap.end_time:.3f}",
                f"FRAME_TIMESTAMPS_SECONDS: {frame_times}",
                "PREVIOUS_CHAPTER:",
                _format_chapter_context(previous) if previous is not None else "(none: this gap is before the first subtitle chapter)",
                "NEXT_CHAPTER:",
                _format_chapter_context(current) if current is not None else "(none: this gap is after the final subtitle chapter)",
                "",
            ]
        )
    return "\n".join(lines)


def _gap_frame_timestamps(gaps: Sequence[VisualGap]) -> tuple[list[float], dict[str, list[float]]]:
    all_timestamps: list[float] = []
    by_gap: dict[str, list[float]] = {}
    for gap in gaps:
        midpoint = _round_time((gap.start_time + gap.end_time) / 2.0)
        timestamps = sorted({_round_time(gap.start_time), midpoint, _round_time(gap.end_time)})
        by_gap[gap.gap_id] = timestamps
        all_timestamps.extend(timestamps)
    return sorted(set(all_timestamps)), by_gap


def _frame_extraction_to_dict(result: FrameExtractionResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, FrameExtractionResult):
        return {
            "backend": result.backend,
            "frame_count": result.frame_count,
            "fallback_reason": result.fallback_reason,
        }
    return dict(result)


def parse_gap_reviews(raw: dict[str, Any], gaps: Sequence[VisualGap]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_reviews = raw.get("gap_reviews") if isinstance(raw, dict) else None
    if not isinstance(raw_reviews, list):
        return [], ["MLLM gap response does not contain a gap_reviews array."]
    valid_gap_ids = {gap.gap_id for gap in gaps}
    reviews: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_reviews, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Gap review #{index} is not an object.")
            continue
        gap_id = str(item.get("gap_id") or "").strip()
        decision = str(item.get("decision") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if gap_id not in valid_gap_ids:
            warnings.append(f"Gap review #{index} has unknown gap_id.")
            continue
        if decision not in {"merge_previous", "merge_next", "standalone"}:
            warnings.append(f"Gap review #{index} has invalid decision.")
            continue
        if not reason:
            warnings.append(f"Gap review #{index} has empty reason.")
            continue
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if decision == "standalone" and (not title or not summary):
            warnings.append(f"Gap review #{index} standalone decision needs title and summary.")
            continue
        seen.add(gap_id)
        reviews.append(
            {
                "gap_id": gap_id,
                "decision": decision,
                "title": title if title else None,
                "summary": summary if summary else None,
                "reason": reason,
            }
        )
    missing = valid_gap_ids - seen
    if missing:
        warnings.append(f"MLLM gap response missed gap ids: {', '.join(sorted(missing))}.")
    return reviews, warnings


def apply_gap_reviews(
    *,
    video_id: str,
    aligned_chapters: Sequence[dict[str, Any]],
    gaps: Sequence[VisualGap],
    reviews: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    chapters = [dict(chapter) for chapter in aligned_chapters]
    review_by_gap_id = {str(review["gap_id"]): review for review in reviews}
    chapter_by_id = {str(chapter["chapter_id"]): chapter for chapter in chapters}
    standalone_chapters: list[dict[str, Any]] = []
    for gap in gaps:
        review = review_by_gap_id.get(gap.gap_id)
        if review is None:
            continue
        if review["decision"] == "merge_previous":
            target = chapter_by_id.get(gap.previous_chapter_id or "")
            if target is None:
                target = chapter_by_id.get(gap.next_chapter_id or "")
                if target is not None:
                    target["start_time"] = gap.start_time
            else:
                target["end_time"] = gap.end_time
            if target is not None:
                target["reason"] = f"{target['reason']} Gap review: {review['reason']}"
        elif review["decision"] == "merge_next":
            target = chapter_by_id.get(gap.next_chapter_id or "")
            if target is None:
                target = chapter_by_id.get(gap.previous_chapter_id or "")
                if target is not None:
                    target["end_time"] = gap.end_time
            else:
                target["start_time"] = gap.start_time
            if target is not None:
                target["reason"] = f"Gap review: {review['reason']} {target['reason']}"
        elif review["decision"] == "standalone":
            standalone_chapters.append(
                {
                    "chapter_id": f"ch_{video_id}_gap_{gap.gap_id[-3:]}",
                    "video_id": video_id,
                    "start_time": gap.start_time,
                    "end_time": gap.end_time,
                    "title": review["title"],
                    "summary": review["summary"],
                    "reason": review["reason"],
                    "importance": 0.5,
                    "source": "visual_gap_mllm",
                    "gap_id": gap.gap_id,
                }
            )
    result = [*chapters, *standalone_chapters]
    result = [chapter for chapter in result if float(chapter["end_time"]) > float(chapter["start_time"])]
    result.sort(key=lambda chapter: (float(chapter["start_time"]), float(chapter["end_time"])))
    for index, chapter in enumerate(result, start=1):
        chapter["chapter_id"] = f"ch_{video_id}_{index:03d}"
    return result


class StoryChapterSubtitleSceneAlignedPipeline:
    def __init__(
        self,
        *,
        llm_client: SubtitleSceneAlignedLlmClientProtocol,
        extract_frames: ExtractFrames = extract_frames_at_timestamps,
        frame_max_height: int = 512,
        max_alignment_window_seconds: float = 10.0,
        min_chapter_seconds: float = 12.0,
        progress_logger: Callable[[str], None] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.extract_frames = extract_frames
        self.frame_max_height = frame_max_height
        self.max_alignment_window_seconds = max_alignment_window_seconds
        self.min_chapter_seconds = min_chapter_seconds
        self.progress_logger = progress_logger

    def _log(self, video_id: str, message: str) -> None:
        if self.progress_logger is not None:
            self.progress_logger(f"[story_chapter_subtitle_scene_aligned] {video_id}: {message}")

    def run(
        self,
        *,
        video_id: str,
        video_path: Path,
        video_metadata: dict[str, Any],
        transcription_path: Path,
        scene_detection_path: Path,
        output_root: Path,
    ) -> Path:
        try:
            video_duration_seconds = float(video_metadata["duration_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("video_metadata.duration_seconds is required for subtitle-scene aligned story chapters.") from exc

        self._log(video_id, "load inputs start")
        utterances = load_utterances_from_transcription(transcription_path)
        scenes = load_scenes(scene_detection_path)
        scene_boundaries = sorted({_round_time(float(scene["start_time"])) for scene in scenes if 0.0 < float(scene["start_time"]) < video_duration_seconds})
        self._log(video_id, f"load inputs done utterances={len(utterances)} scenes={len(scenes)} scene_boundaries={len(scene_boundaries)}")

        self._log(video_id, "subtitle draft LLM start")
        raw = self.llm_client.generate_json_multimodal(
            system_prompt=build_draft_chapter_system_prompt(),
            user_prompt=build_draft_chapter_user_prompt(
                video_id=video_id,
                video_duration_seconds=video_duration_seconds,
                utterances=utterances,
            ),
            max_tokens=3200,
        )
        drafts, parse_warnings = parse_draft_chapters(raw)
        self._log(video_id, f"subtitle draft LLM done drafts={len(drafts)} warnings={len(parse_warnings)}")

        aligned_chapters, align_warnings = align_draft_chapters_to_scene_boundaries(
            video_id=video_id,
            video_duration_seconds=video_duration_seconds,
            scenes=scenes,
            drafts=drafts,
            max_alignment_window_seconds=self.max_alignment_window_seconds,
            min_chapter_seconds=self.min_chapter_seconds,
        )
        aligned_chapters, normalize_warnings = normalize_aligned_chapters(aligned_chapters)
        align_warnings.extend(normalize_warnings)
        self._log(video_id, f"scene alignment done chapters={len(aligned_chapters)} warnings={len(align_warnings)}")

        visual_gaps = find_visual_gaps(aligned_chapters, video_duration_seconds=video_duration_seconds)
        self._log(video_id, f"visual gap discovery done gaps={len(visual_gaps)}")
        gap_raw: dict[str, Any] = {"gap_reviews": []}
        gap_reviews: list[dict[str, Any]] = []
        gap_warnings: list[str] = []
        frame_extraction: dict[str, Any] | None = None
        frame_timestamps_by_gap: dict[str, list[float]] = {}
        frame_timestamps_seconds: list[float] = []
        if visual_gaps:
            frame_timestamps_seconds, frame_timestamps_by_gap = _gap_frame_timestamps(visual_gaps)
            self._log(
                video_id,
                f"gap frame extraction start gaps={len(visual_gaps)} frame_timestamps={len(frame_timestamps_seconds)} max_height={self.frame_max_height}",
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                frame_dir = Path(tmpdir) / "gap_frames"
                extraction_result = self.extract_frames(
                    video_path=video_path,
                    output_dir=frame_dir,
                    timestamps_seconds=frame_timestamps_seconds,
                    max_height=self.frame_max_height,
                )
                frame_extraction = _frame_extraction_to_dict(extraction_result)
                image_paths = sorted(frame_dir.glob("*.png"))
                self._log(
                    video_id,
                    f"gap frame extraction done input_frames={len(frame_timestamps_seconds)} extracted_images={len(image_paths)}",
                )
                chapters_by_id = {str(chapter["chapter_id"]): chapter for chapter in aligned_chapters}
                self._log(
                    video_id,
                    f"gap MLLM review start gaps={len(visual_gaps)} input_frames={len(image_paths)}",
                )
                gap_raw = self.llm_client.generate_json_multimodal(
                    system_prompt=build_gap_review_system_prompt(),
                    user_prompt=build_gap_review_user_prompt(
                        video_id=video_id,
                        gaps=visual_gaps,
                        chapters_by_id=chapters_by_id,
                        frame_timestamps_by_gap=frame_timestamps_by_gap,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=frame_timestamps_seconds,
                    max_tokens=3200,
                )
                gap_reviews, gap_warnings = parse_gap_reviews(gap_raw, visual_gaps)
                self._log(video_id, f"gap MLLM review done reviews={len(gap_reviews)} warnings={len(gap_warnings)}")

        story_chapters = apply_gap_reviews(
            video_id=video_id,
            aligned_chapters=aligned_chapters,
            gaps=visual_gaps,
            reviews=gap_reviews,
        )
        self._log(video_id, f"gap review merge done chapters={len(story_chapters)} warnings={len(gap_warnings)}")

        output_dir = output_root / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "story_chapters.json"
        output = {
            "video_id": video_id,
            "created_at": _now_iso(),
            "generation_mode": "subtitle_scene_aligned",
            "video_path": str(video_path),
            "video_metadata": {"duration_seconds": _round_time(video_duration_seconds)},
            "source": {
                "transcription_path": str(transcription_path),
                "scene_detection_path": str(scene_detection_path),
            },
            "utterances": [asdict(utterance) for utterance in utterances],
            "scenes": list(scenes),
            "scene_boundaries": list(scene_boundaries),
            "subtitle_chapters": [asdict(draft) for draft in drafts],
            "aligned_subtitle_chapters": aligned_chapters,
            "visual_gaps": [asdict(gap) for gap in visual_gaps],
            "frame_timestamps_seconds": frame_timestamps_seconds,
            "frame_timestamps_by_gap": frame_timestamps_by_gap,
            "frame_extraction": frame_extraction,
            "gap_reviews": gap_reviews,
            "gap_review_raw": gap_raw,
            "draft_chapters": [asdict(draft) for draft in drafts],
            "llm_raw": raw,
            "story_chapters": story_chapters,
            "warnings": [*parse_warnings, *align_warnings, *gap_warnings],
        }
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._log(video_id, f"write output done path={output_path}")
        return output_path


__all__ = [
    "DraftChapter",
    "StoryChapterSubtitleSceneAlignedPipeline",
    "align_draft_chapters_to_scene_boundaries",
    "build_draft_chapter_system_prompt",
    "build_draft_chapter_user_prompt",
    "build_gap_review_system_prompt",
    "build_gap_review_user_prompt",
    "find_visual_gaps",
    "parse_gap_reviews",
    "parse_draft_chapters",
]

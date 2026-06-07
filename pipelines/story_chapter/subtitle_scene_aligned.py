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


ExtractFrames = Callable[..., FrameExtractionResult | dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_frame_time(value: float) -> float:
    return round(float(value), 1)


def _clamp_importance(value: Any) -> float:
    number = _safe_float(value)
    if number is None:
        return 0.5
    return max(0.0, min(1.0, number))


def _format_utterance_line(utterance: Utterance) -> str:
    if isinstance(utterance, dict):
        speaker_id = utterance.get("speaker_id")
        speaker = f" speaker={speaker_id}" if speaker_id is not None else ""
        return (
            f"{utterance['utterance_id']} "
            f"[{float(utterance['start_time']):.3f}-{float(utterance['end_time']):.3f}]"
            f"{speaker}: {utterance['text']}"
        )
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
    frame_timestamps_seconds: Sequence[float] | None = None,
) -> str:
    utterance_lines = "\n".join(_format_utterance_line(utterance) for utterance in utterances)
    frame_lines = ", ".join(f"{timestamp:.3f}" for timestamp in frame_timestamps_seconds or [])
    return "\n".join(
        [
            "## TASK",
            "Read the full subtitle transcript and decide the semantic story chapters.",
            "Sparse video frames may be attached as visual anchors. Use them to avoid placing chapter starts/ends too early when visual action, location changes, or silent transitions continue after the nearest subtitle.",
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
            "## SPARSE_VIDEO_FRAMES",
            f"FRAME_TIMESTAMPS_SECONDS: {frame_lines or '(no frames attached)'}",
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


def draft_frame_timestamps(
    *,
    video_duration_seconds: float,
    interval_seconds: float = 10.0,
) -> list[float]:
    if video_duration_seconds <= 0.0 or interval_seconds <= 0.0:
        return []
    timestamps: list[float] = []
    current = 0.0
    while current < video_duration_seconds:
        timestamps.append(_round_time(current))
        current += interval_seconds
    return sorted(set(timestamps))


def subtitle_chapters_from_drafts(
    *,
    video_id: str,
    drafts: Sequence[DraftChapter],
) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    for index, draft in enumerate(drafts, start=1):
        chapters.append(
            {
                "chapter_id": f"ch_{video_id}_{index:03d}",
                "video_id": video_id,
                "start_time": draft.start_time,
                "end_time": draft.end_time,
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
                },
            }
        )
    return chapters


def _boundary_search_time_range(
    *,
    previous_chapter: dict[str, Any],
    next_chapter: dict[str, Any],
    video_duration_seconds: float,
    context_seconds: float = 10.0,
) -> dict[str, float]:
    rough_start = min(float(previous_chapter["end_time"]), float(next_chapter["start_time"]))
    rough_end = max(float(previous_chapter["end_time"]), float(next_chapter["start_time"]))
    return {
        "start_time": _round_time(max(0.0, rough_start - context_seconds)),
        "end_time": _round_time(min(video_duration_seconds, rough_end + context_seconds)),
    }


def boundary_subtitle_context(
    *,
    search_time_range: dict[str, float],
    utterances: Sequence[Utterance],
) -> tuple[list[Utterance], dict[str, float]]:
    start_time = _round_time(float(search_time_range["start_time"]))
    end_time = _round_time(float(search_time_range["end_time"]))
    context = [
        utterance
        for utterance in utterances
        if utterance.end_time >= start_time and utterance.start_time <= end_time
    ]
    return context, {"start_time": start_time, "end_time": end_time}


def _chapter_subtitle_context(*, chapter: dict[str, Any], utterances: Sequence[Utterance]) -> list[Utterance]:
    start_time = float(chapter["start_time"])
    end_time = float(chapter["end_time"])
    return [
        utterance
        for utterance in utterances
        if utterance.end_time >= start_time and utterance.start_time <= end_time
    ]


def boundary_frame_timestamps(
    boundary_reviews: Sequence[dict[str, Any]],
    *,
    video_duration_seconds: float,
) -> tuple[list[float], dict[str, list[float]]]:
    all_timestamps: list[float] = []
    by_boundary: dict[str, list[float]] = {}
    for review in boundary_reviews:
        search_range = review.get("search_time_range") or {}
        start_time = _round_frame_time(max(0.0, float(search_range.get("start_time", 0.0))))
        end_time = _round_frame_time(min(video_duration_seconds, float(search_range.get("end_time", video_duration_seconds))))
        timestamps: list[float] = []
        current = start_time
        while current <= end_time + 1e-9:
            timestamps.append(_round_frame_time(current))
            current += 1.0
        if timestamps and timestamps[-1] != end_time:
            timestamps.append(end_time)
        timestamps = sorted(set(timestamps))
        by_boundary[str(review["boundary_id"])] = timestamps
        all_timestamps.extend(timestamps)
    return sorted(set(all_timestamps)), by_boundary


def build_boundary_review_system_prompt() -> str:
    return (
        "You are a multimodal short-drama chapter boundary editor. "
        "Find the exact frame timestamp that separates two adjacent story events. "
        "Return valid JSON only."
    )


def build_boundary_review_user_prompt(
    *,
    video_id: str,
    boundary_review: dict[str, Any],
    frame_timestamps_seconds: list[float],
) -> str:
    frame_times = ", ".join(f"{timestamp:.1f}" for timestamp in frame_timestamps_seconds)
    lines = [
        "## TASK",
        "There is exactly one story chapter boundary inside the search time range below.",
        "You are given subtitles from the previous subtitle chapter, subtitles from the next subtitle chapter, nearby subtitles, and sampled video frames.",
        "Use subtitles to understand story meaning, but choose the boundary by visual evidence in the frames.",
        "Choose the earliest frame timestamp where the visual state has already changed into the next story event.",
        "Focus on scene changes, location changes, character grouping changes, action goal changes, and visual transition timing.",
        "",
        "Boundary principle:",
        "- Everything before boundary_time belongs to the previous chapter.",
        "- Everything from boundary_time onward belongs to the next chapter.",
        "- The subtitle chapter ranges are rough semantic anchors, not hard timing constraints.",
        "- Subtitles are semantic context, not timing targets.",
        "- Do not choose a timestamp only because a subtitle line starts there.",
        "- If the image changes before the first subtitle of the next story event, choose the visual change frame, not the subtitle start frame.",
        "- The true boundary may appear before the previous subtitle chapter's last line or after the next subtitle chapter's first line.",
        "- Prefer the frame where the visual/story state has clearly switched, not merely the first ambiguous transition frame.",
        "",
        "## OUTPUT JSON",
        "Return exactly this shape:",
        '{"boundary_reviews":[{"boundary_id":"br_001","boundary_time":83.6,"reason":"该帧之后地点和行动目标切换，剧情进入返乡段落。"}]}',
        "Rules:",
        "- Return exactly one review for the boundary_id below.",
        "- boundary_time must be one of FRAME_TIMESTAMPS_SECONDS because those are the frames you can see.",
        "- reason is required and should explain visual/story evidence.",
        "",
        f"## VIDEO_ID\n{video_id}",
        "",
        "## BOUNDARY_TASK",
        f"BOUNDARY_ID: {boundary_review['boundary_id']}",
        f"SEARCH_TIME_RANGE_SECONDS: {float(boundary_review.get('search_time_range', {}).get('start_time', 0.0)):.1f}-{float(boundary_review.get('search_time_range', {}).get('end_time', 0.0)):.1f}",
        f"FRAME_TIMESTAMPS_SECONDS: {frame_times}",
        "",
        "PREVIOUS_CHAPTER_SUBTITLES:",
        *(_format_utterance_line(utterance) for utterance in boundary_review.get("previous_chapter_subtitles", [])),
        "",
        "NEXT_CHAPTER_SUBTITLES:",
        *(_format_utterance_line(utterance) for utterance in boundary_review.get("next_chapter_subtitles", [])),
        "",
        "BOUNDARY_SUBTITLE_CONTEXT:",
        f"TIME_RANGE: {float(boundary_review.get('subtitle_context_time_range', {}).get('start_time', 0.0)):.3f}-{float(boundary_review.get('subtitle_context_time_range', {}).get('end_time', 0.0)):.3f}",
        *(_format_utterance_line(utterance) for utterance in boundary_review.get("subtitle_context", [])),
    ]
    return "\n".join(lines)


def parse_boundary_reviews(
    raw: dict[str, Any],
    *,
    valid_boundary_ids: set[str],
    frame_times_by_boundary: dict[str, set[float]],
    frame_time_tolerance_seconds: float = 0.25,
) -> tuple[list[dict[str, Any]], list[str]]:
    raw_reviews = raw.get("boundary_reviews") if isinstance(raw, dict) else None
    if not isinstance(raw_reviews, list):
        return [], ["MLLM boundary response does not contain a boundary_reviews array."]
    reviews: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_reviews, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Boundary review #{index} is not an object.")
            continue
        boundary_id = str(item.get("boundary_id") or "").strip()
        boundary_time = _safe_float(item.get("boundary_time"))
        reason = str(item.get("reason") or "").strip()
        if boundary_id not in valid_boundary_ids:
            warnings.append(f"Boundary review #{index} has unknown boundary_id.")
            continue
        if boundary_time is None:
            warnings.append(f"Boundary review #{index} has invalid boundary_time.")
            continue
        rounded_time = _round_frame_time(boundary_time)
        valid_frame_times = frame_times_by_boundary.get(boundary_id, set())
        if rounded_time not in valid_frame_times:
            nearest_time = min(valid_frame_times, key=lambda time: abs(time - rounded_time)) if valid_frame_times else None
            if nearest_time is not None and abs(nearest_time - rounded_time) <= frame_time_tolerance_seconds:
                rounded_time = _round_frame_time(nearest_time)
            else:
                warnings.append(f"Boundary review #{index} boundary_time is not one of the sampled frame timestamps.")
                continue
        if rounded_time not in valid_frame_times:
            warnings.append(f"Boundary review #{index} boundary_time is not one of the sampled frame timestamps.")
            continue
        if not reason:
            warnings.append(f"Boundary review #{index} has empty reason.")
            continue
        seen.add(boundary_id)
        reviews.append({"boundary_id": boundary_id, "boundary_time": rounded_time, "reason": reason})
    missing = valid_boundary_ids - seen
    if missing:
        warnings.append(f"MLLM boundary response missed boundary ids: {', '.join(sorted(missing))}.")
    return reviews, warnings


def build_boundary_review_tasks(
    *,
    aligned_chapters: Sequence[dict[str, Any]],
    utterances: Sequence[Utterance],
    video_duration_seconds: float,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for previous, current in zip(aligned_chapters, aligned_chapters[1:]):
        search_time_range = _boundary_search_time_range(
            previous_chapter=previous,
            next_chapter=current,
            video_duration_seconds=video_duration_seconds,
        )
        subtitle_context, subtitle_context_time_range = boundary_subtitle_context(
            search_time_range=search_time_range,
            utterances=utterances,
        )
        tasks.append(
            {
                "boundary_id": f"br_{len(tasks) + 1:03d}",
                "previous_chapter": previous,
                "next_chapter": current,
                "search_time_range": search_time_range,
                "previous_chapter_subtitles": [asdict(utterance) for utterance in _chapter_subtitle_context(chapter=previous, utterances=utterances)],
                "next_chapter_subtitles": [asdict(utterance) for utterance in _chapter_subtitle_context(chapter=current, utterances=utterances)],
                "subtitle_context": [asdict(utterance) for utterance in subtitle_context],
                "subtitle_context_time_range": subtitle_context_time_range,
            }
        )
    return tasks


def build_final_chapters_from_boundary_reviews(
    *,
    video_id: str,
    video_duration_seconds: float,
    aligned_chapters: Sequence[dict[str, Any]],
    boundary_tasks: Sequence[dict[str, Any]],
    boundary_reviews: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_by_id = {str(review["boundary_id"]): review for review in boundary_reviews}
    boundaries: list[float] = []
    for task in boundary_tasks:
        review = review_by_id.get(str(task["boundary_id"]))
        if review is None:
            frame_timestamps = list(task.get("frame_timestamps_seconds") or [])
            if frame_timestamps:
                boundaries.append(float(frame_timestamps[len(frame_timestamps) // 2]))
                continue
            search_range = task.get("search_time_range") or {}
            boundaries.append((float(search_range.get("start_time", 0.0)) + float(search_range.get("end_time", video_duration_seconds))) / 2.0)
        else:
            boundaries.append(float(review["boundary_time"]))
    points = [0.0, *sorted(set(_round_time(boundary) for boundary in boundaries)), _round_time(video_duration_seconds)]
    chapters: list[dict[str, Any]] = []
    for index, draft in enumerate(aligned_chapters, start=1):
        if index >= len(points):
            break
        start_time = points[index - 1]
        end_time = points[index]
        if end_time <= start_time:
            continue
        chapter = dict(draft)
        chapter["chapter_id"] = f"ch_{video_id}_{len(chapters) + 1:03d}"
        chapter["video_id"] = video_id
        chapter["start_time"] = start_time
        chapter["end_time"] = end_time
        chapters.append(chapter)
    return chapters


def _frame_extraction_to_dict(result: FrameExtractionResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, FrameExtractionResult):
        return {
            "backend": result.backend,
            "frame_count": result.frame_count,
            "fallback_reason": result.fallback_reason,
        }
    return dict(result)


class StoryChapterSubtitleSceneAlignedPipeline:
    def __init__(
        self,
        *,
        llm_client: SubtitleSceneAlignedLlmClientProtocol,
        extract_frames: ExtractFrames = extract_frames_at_timestamps,
        frame_max_height: int = 512,
        draft_frame_interval_seconds: float = 10.0,
        progress_logger: Callable[[str], None] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.extract_frames = extract_frames
        self.frame_max_height = frame_max_height
        self.draft_frame_interval_seconds = draft_frame_interval_seconds
        self.progress_logger = progress_logger

    def _log(self, video_id: str, message: str) -> None:
        if self.progress_logger is not None:
            self.progress_logger(f"[story_chapter_subtitle_scene_aligned] {video_id}: {message}")

    def run(
        self,
        *,
        video_id: str,
        series_id: str | None = None,
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

        draft_frame_timestamps_seconds = draft_frame_timestamps(
            video_duration_seconds=video_duration_seconds,
            interval_seconds=self.draft_frame_interval_seconds,
        )
        draft_frame_extraction: dict[str, Any] | None = None
        draft_image_paths: list[Path] = []
        self._log(video_id, "subtitle draft LLM start")
        if draft_frame_timestamps_seconds:
            self._log(
                video_id,
                f"subtitle draft frame extraction start input_frames={len(draft_frame_timestamps_seconds)} interval_seconds={self.draft_frame_interval_seconds:g} max_height={self.frame_max_height}",
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                draft_frame_dir = Path(tmpdir) / "draft_frames"
                extraction_result = self.extract_frames(
                    video_path=video_path,
                    output_dir=draft_frame_dir,
                    timestamps_seconds=draft_frame_timestamps_seconds,
                    max_height=self.frame_max_height,
                )
                draft_frame_extraction = _frame_extraction_to_dict(extraction_result)
                draft_image_paths = sorted(draft_frame_dir.glob("*.png"))
                draft_frame_extraction["input_frame_count"] = len(draft_frame_timestamps_seconds)
                draft_frame_extraction["extracted_image_count"] = len(draft_image_paths)
                self._log(
                    video_id,
                    f"subtitle draft frame extraction done input_frames={len(draft_frame_timestamps_seconds)} extracted_images={len(draft_image_paths)}",
                )
                raw = self.llm_client.generate_json_multimodal(
                    system_prompt=build_draft_chapter_system_prompt(),
                    user_prompt=build_draft_chapter_user_prompt(
                        video_id=video_id,
                        video_duration_seconds=video_duration_seconds,
                        utterances=utterances,
                        frame_timestamps_seconds=draft_frame_timestamps_seconds,
                    ),
                    image_paths=draft_image_paths,
                    frame_timestamps_seconds=draft_frame_timestamps_seconds,
                    max_tokens=3200,
                )
        else:
            raw = self.llm_client.generate_json_multimodal(
                system_prompt=build_draft_chapter_system_prompt(),
                user_prompt=build_draft_chapter_user_prompt(
                    video_id=video_id,
                    video_duration_seconds=video_duration_seconds,
                    utterances=utterances,
                    frame_timestamps_seconds=draft_frame_timestamps_seconds,
                ),
                max_tokens=3200,
            )
        drafts, parse_warnings = parse_draft_chapters(raw)
        self._log(video_id, f"subtitle draft LLM done drafts={len(drafts)} warnings={len(parse_warnings)}")
        subtitle_chapters = subtitle_chapters_from_drafts(video_id=video_id, drafts=drafts)

        boundary_tasks = build_boundary_review_tasks(
            aligned_chapters=subtitle_chapters,
            utterances=utterances,
            video_duration_seconds=video_duration_seconds,
        )
        self._log(video_id, f"boundary review task build done boundaries={len(boundary_tasks)}")
        boundary_raw: dict[str, Any] = {"boundary_review_calls": {}}
        boundary_reviews: list[dict[str, Any]] = []
        boundary_warnings: list[str] = []
        frame_extraction: dict[str, Any] | None = None
        frame_timestamps_by_boundary: dict[str, list[float]] = {}
        frame_timestamps_seconds: list[float] = []
        if boundary_tasks:
            frame_extraction = {"per_boundary": {}, "frame_count": 0}
            for task in boundary_tasks:
                boundary_id = str(task["boundary_id"])
                task_frame_timestamps, task_frame_timestamps_by_boundary = boundary_frame_timestamps(
                    [task],
                    video_duration_seconds=video_duration_seconds,
                )
                task["frame_timestamps_seconds"] = task_frame_timestamps
                frame_timestamps_by_boundary.update(task_frame_timestamps_by_boundary)
                frame_timestamps_seconds.extend(task_frame_timestamps)
                self._log(
                    video_id,
                    f"boundary frame extraction start boundary_id={boundary_id} input_frames={len(task_frame_timestamps)} max_height={self.frame_max_height}",
                )
                with tempfile.TemporaryDirectory() as tmpdir:
                    frame_dir = Path(tmpdir) / boundary_id
                    extraction_result = self.extract_frames(
                        video_path=video_path,
                        output_dir=frame_dir,
                        timestamps_seconds=task_frame_timestamps,
                        max_height=self.frame_max_height,
                    )
                    extraction_dict = _frame_extraction_to_dict(extraction_result)
                    image_paths = sorted(frame_dir.glob("*.png"))
                    extraction_dict["input_frame_count"] = len(task_frame_timestamps)
                    extraction_dict["extracted_image_count"] = len(image_paths)
                    frame_extraction["per_boundary"][boundary_id] = extraction_dict
                    frame_extraction["frame_count"] = int(frame_extraction["frame_count"]) + len(image_paths)
                    self._log(
                        video_id,
                        f"boundary frame extraction done boundary_id={boundary_id} input_frames={len(task_frame_timestamps)} extracted_images={len(image_paths)}",
                    )
                    self._log(
                        video_id,
                        f"boundary MLLM review start boundary_id={boundary_id} input_frames={len(image_paths)}",
                    )
                    task_raw = self.llm_client.generate_json_multimodal(
                        system_prompt=build_boundary_review_system_prompt(),
                        user_prompt=build_boundary_review_user_prompt(
                            video_id=video_id,
                            boundary_review=task,
                            frame_timestamps_seconds=task_frame_timestamps,
                        ),
                        image_paths=image_paths,
                        frame_timestamps_seconds=task_frame_timestamps,
                        max_tokens=1600,
                    )
                    boundary_raw["boundary_review_calls"][boundary_id] = task_raw
                    parsed_reviews, parsed_warnings = parse_boundary_reviews(
                        task_raw,
                        valid_boundary_ids={boundary_id},
                        frame_times_by_boundary={boundary_id: set(task_frame_timestamps)},
                    )
                    boundary_reviews.extend(parsed_reviews)
                    boundary_warnings.extend(parsed_warnings)
                    self._log(
                        video_id,
                        f"boundary MLLM review done boundary_id={boundary_id} reviews={len(parsed_reviews)} warnings={len(parsed_warnings)}",
                    )
            frame_timestamps_seconds = sorted(set(frame_timestamps_seconds))

        story_chapters = build_final_chapters_from_boundary_reviews(
            video_id=video_id,
            video_duration_seconds=video_duration_seconds,
            aligned_chapters=subtitle_chapters,
            boundary_tasks=boundary_tasks,
            boundary_reviews=boundary_reviews,
        )
        self._log(video_id, f"boundary review merge done chapters={len(story_chapters)} warnings={len(boundary_warnings)}")

        output_dir = output_root / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "story_chapters.json"
        debug_output_path = output_dir / "story_chapters.debug.json"
        clean_chapters = [
            {
                "chapter_id": chapter["chapter_id"],
                "start_time": chapter["start_time"],
                "end_time": chapter["end_time"],
                "title": chapter["title"],
                "summary": chapter["summary"],
                "reason": chapter["reason"],
            }
            for chapter in story_chapters
        ]
        created_at = _now_iso()
        clean_output = {
            "video_id": video_id,
            "series_id": series_id,
            "created_at": created_at,
            "story_chapters": clean_chapters,
        }
        debug_output = {
            "video_id": video_id,
            "series_id": series_id,
            "created_at": created_at,
            "generation_mode": "subtitle_scene_aligned",
            "video_path": str(video_path),
            "clean_output_path": str(output_path),
            "video_metadata": {"duration_seconds": _round_time(video_duration_seconds)},
            "source": {
                "transcription_path": str(transcription_path),
                "scene_detection_path": str(scene_detection_path),
            },
            "utterances": [asdict(utterance) for utterance in utterances],
            "scenes": list(scenes),
            "scene_boundaries": list(scene_boundaries),
            "subtitle_chapters": subtitle_chapters,
            "draft_frame_timestamps_seconds": draft_frame_timestamps_seconds,
            "draft_frame_extraction": draft_frame_extraction,
            "boundary_review_tasks": boundary_tasks,
            "frame_timestamps_seconds": frame_timestamps_seconds,
            "frame_timestamps_by_boundary": frame_timestamps_by_boundary,
            "frame_extraction": frame_extraction,
            "boundary_reviews": boundary_reviews,
            "boundary_review_raw": boundary_raw,
            "draft_chapters": [asdict(draft) for draft in drafts],
            "llm_raw": raw,
            "story_chapters": story_chapters,
            "warnings": [*parse_warnings, *boundary_warnings],
        }
        output_path.write_text(json.dumps(clean_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        debug_output_path.write_text(json.dumps(debug_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._log(video_id, f"write output done path={output_path}")
        return output_path


__all__ = [
    "DraftChapter",
    "StoryChapterSubtitleSceneAlignedPipeline",
    "build_boundary_review_system_prompt",
    "build_boundary_review_user_prompt",
    "build_draft_chapter_system_prompt",
    "build_draft_chapter_user_prompt",
    "build_final_chapters_from_boundary_reviews",
    "boundary_frame_timestamps",
    "draft_frame_timestamps",
    "parse_boundary_reviews",
    "parse_draft_chapters",
    "subtitle_chapters_from_drafts",
]

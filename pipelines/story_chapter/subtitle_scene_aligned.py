from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from pipelines.story_chapter.baseline_text import Utterance, _round_time, load_scenes, load_utterances_from_transcription


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
    end_time: float
    title: str
    summary: str
    importance: float
    end_utterance_id: str | None = None


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
    return f"{utterance.utterance_id} [{utterance.start_time:.3f}-{utterance.end_time:.3f}]: {utterance.text}"


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
            "For each chapter, choose the subtitle utterance that ends this chapter.",
            "Use that subtitle utterance's end time as `end_time`; do not invent an approximate boundary time.",
            "The final chapter should use VIDEO_DURATION_SECONDS as end_time if the story continues after the final subtitle.",
            "",
            "## OUTPUT JSON",
            "Return exactly this shape:",
            '{"chapters":[{"end_utterance_id":"u_018","end_time":83.5,"title":"讨薪成功","summary":"工人讨薪并拿到工钱。","importance":0.7}]}',
            "",
            "Rules:",
            "- chapters must cover the whole episode in order.",
            "- end_time must be copied from the chosen ending subtitle's end time, except the final chapter may end at VIDEO_DURATION_SECONDS.",
            "- end_time must be increasing.",
            "- end_utterance_id must be the utterance_id of the subtitle that ends this chapter, or null only for the final chapter if it ends after the final subtitle.",
            "- Do not output start_time.",
            "- Use 3-5 chapters for a typical short episode unless the story strongly requires otherwise.",
            "- title should be short and useful for player navigation.",
            "- summary should describe the chapter ending at end_time.",
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
        end_time = _safe_float(item.get("end_time"))
        if end_time is None or end_time <= 0:
            warnings.append(f"Chapter draft #{index} has invalid end_time.")
            continue
        if end_time <= previous_end:
            warnings.append(f"Chapter draft #{index} end_time is not increasing.")
            continue
        previous_end = end_time
        end_utterance_id = item.get("end_utterance_id")
        drafts.append(
            DraftChapter(
                end_time=_round_time(end_time),
                title=str(item.get("title") or f"章节 {len(drafts) + 1}").strip(),
                summary=str(item.get("summary") or "").strip(),
                importance=_clamp_importance(item.get("importance", 0.5)),
                end_utterance_id=str(end_utterance_id).strip() if end_utterance_id is not None else None,
            )
        )
    return drafts, warnings


def _scene_end_containing_time(time_sec: float, scenes: Sequence[dict[str, Any]]) -> float | None:
    for scene in scenes:
        try:
            start_time = float(scene["start_time"])
            end_time = float(scene["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < time_sec <= end_time or start_time <= time_sec < end_time:
            return _round_time(end_time)
    return None


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
                "alignment": {"subtitle_end_time": _round_time(video_duration_seconds), "aligned_scene_end_time": None},
            }
        ], ["No valid subtitle draft chapters; generated one full-episode fallback chapter."]

    selected_boundaries: list[float] = []
    for index, draft in enumerate(drafts[:-1], start=1):
        chosen = _scene_end_containing_time(draft.end_time, scenes)
        if chosen is None:
            warnings.append(f"Could not find containing scene for draft chapter #{index} end_time={draft.end_time:.3f}.")
            continue
        selected_boundaries.append(chosen)

    points = [0.0, *selected_boundaries, _round_time(video_duration_seconds)]
    chapters: list[dict[str, Any]] = []
    for index, (start_time, end_time) in enumerate(zip(points, points[1:]), start=1):
        draft = drafts[min(index - 1, len(drafts) - 1)]
        aligned_boundary = end_time if index <= len(selected_boundaries) else None
        chapters.append(
            {
                "chapter_id": f"ch_{video_id}_{index:03d}",
                "video_id": video_id,
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "title": draft.title,
                "summary": draft.summary,
                "reason": "Subtitle ending line aligned to the end of its containing scene.",
                "importance": draft.importance,
                "alignment": {
                    "end_utterance_id": draft.end_utterance_id,
                    "subtitle_end_time": draft.end_time,
                    "aligned_scene_end_time": aligned_boundary,
                    "alignment_error_seconds": _round_time(aligned_boundary - draft.end_time)
                    if aligned_boundary is not None
                    else None,
                },
            }
        )
    return chapters, warnings


class StoryChapterSubtitleSceneAlignedPipeline:
    def __init__(
        self,
        *,
        llm_client: SubtitleSceneAlignedLlmClientProtocol,
        max_alignment_window_seconds: float = 10.0,
        min_chapter_seconds: float = 12.0,
        progress_logger: Callable[[str], None] | None = None,
    ) -> None:
        self.llm_client = llm_client
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

        story_chapters, align_warnings = align_draft_chapters_to_scene_boundaries(
            video_id=video_id,
            video_duration_seconds=video_duration_seconds,
            scenes=scenes,
            drafts=drafts,
            max_alignment_window_seconds=self.max_alignment_window_seconds,
            min_chapter_seconds=self.min_chapter_seconds,
        )
        self._log(video_id, f"scene alignment done chapters={len(story_chapters)} warnings={len(align_warnings)}")

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
            "draft_chapters": [asdict(draft) for draft in drafts],
            "llm_raw": raw,
            "story_chapters": story_chapters,
            "warnings": [*parse_warnings, *align_warnings],
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
    "parse_draft_chapters",
]

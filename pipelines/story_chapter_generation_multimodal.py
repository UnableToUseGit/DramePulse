from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Protocol, Sequence

from pipelines.story_chapter_generation import (
    Utterance,
    _round_time,
    format_utterance_timeline,
    load_utterances_from_transcription,
    parse_chapter_drafts,
)
from pipelines.utils import FrameExtractionResult, extract_frames_at_timestamps


class MultimodalLlmClientProtocol(Protocol):
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


ExtractFrames = Callable[..., FrameExtractionResult | dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _video_duration_from_metadata(video_metadata: dict[str, Any]) -> float:
    try:
        duration = float(video_metadata["duration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("video_metadata.duration_seconds is required for multimodal story chapter generation.") from exc
    if duration <= 0:
        raise ValueError("video_metadata.duration_seconds must be greater than 0.")
    return _round_time(duration)


def _uniform_downsample(values: list[float], max_items: int) -> list[float]:
    if max_items <= 0:
        raise ValueError("max_frames must be positive.")
    if len(values) <= max_items:
        return values
    if max_items == 1:
        return [values[0]]
    last_index = len(values) - 1
    indexes = [round(index * last_index / (max_items - 1)) for index in range(max_items)]
    return [values[index] for index in indexes]


def build_frame_timestamps(
    video_duration_seconds: float,
    *,
    frame_interval_seconds: float = 1.0,
    max_frames: int | None = 120,
) -> list[float]:
    duration = _round_time(video_duration_seconds)
    if duration < 0:
        raise ValueError("video_duration_seconds must be non-negative.")
    if frame_interval_seconds <= 0:
        raise ValueError("frame_interval_seconds must be positive.")
    timestamps: list[float] = []
    current = 0.0
    while current <= duration:
        timestamps.append(_round_time(current))
        current = _round_time(current + frame_interval_seconds)
    if not timestamps:
        timestamps = [0.0]
    if max_frames is not None:
        return _uniform_downsample(timestamps, max_frames)
    return timestamps


def build_multimodal_system_prompt() -> str:
    return (
        "You are a multimodal story structure analyst for short-drama timeline navigation. "
        "Use both the sampled video frames and timestamped utterances. "
        "Return valid JSON only, with no markdown or explanatory text."
    )


def _format_frame_timestamps(frame_timestamps_seconds: Sequence[float]) -> str:
    return ", ".join(f"{timestamp:.3f}" for timestamp in frame_timestamps_seconds)


def build_multimodal_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    frame_timestamps_seconds: Sequence[float],
) -> str:
    return "\n".join(
        [
            "## TASK",
            "Split the full short-drama video timeline into continuous story chapters for player navigation.",
            "Use video frames and subtitles together to produce the strongest possible chapter segmentation.",
            "A story chapter is a coherent narrative segment that helps a viewer understand what this part of the episode is about.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {_round_time(video_duration_seconds):.3f}",
            f"FRAME_TIMESTAMPS_SECONDS: {_format_frame_timestamps(frame_timestamps_seconds)}",
            "You will receive one sampled video frame for each timestamp listed above.",
            "You will also receive a timestamped utterance timeline.",
            "",
            "## RULES",
            "- Use video frames to understand silent sections, actions, facial expressions, locations, transitions, and visible story situations.",
            "- Use subtitles to understand dialogue, relationship context, and semantic plot progression.",
            "- Chapters must cover the full video timeline from 0.0 to VIDEO_DURATION_SECONDS.",
            "- Do not leave gaps between adjacent chapters. The `end_time` of one chapter should match the `start_time` of the next chapter.",
            "- Overlap is not allowed.",
            "- Treat chapter ranges as left-closed and right-open: [start_time, end_time), except the final chapter ends at VIDEO_DURATION_SECONDS.",
            "- If a boundary is at time `t`, the utterance starting at `t` belongs to the next chapter that starts at `t`, not the previous chapter.",
            "- Internal chapter boundaries must be selected from FRAME_TIMESTAMPS_SECONDS.",
            "- The first chapter must start at 0.0.",
            "- The final chapter end_time must be VIDEO_DURATION_SECONDS, even if VIDEO_DURATION_SECONDS is not a frame timestamp.",
            "- Do not output interaction triggers, highlight moments, poll options, danmaku, audience emotions, or user feedback opportunities.",
            "- `title` should sound like a natural short-drama timeline label, not a story-analysis category.",
            "- Avoid abstract structural titles such as 开局设定、冲突升级、关系变化、反转揭露、高潮收束.",
            "- Prefer concrete plot labels grounded in characters, actions, objects, places, or visible story situations.",
            "- `title` should be short Chinese, preferably 4 to 8 Chinese characters.",
            "- `summary` should be one concise factual Chinese sentence grounded in subtitles and/or frames.",
            "- `importance` should reflect how important the chapter is for understanding the episode, from 0.0 to 1.0.",
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `chapters`.",
            "Each chapter object must contain exactly these keys: `start_time`, `end_time`, `title`, `summary`, `importance`.",
            "Output shape:",
            '{"chapters":[{"start_time":0.0,"end_time":18.0,"title":"债主堵门","summary":"债主上门逼债，主角试图保护家人。","importance":0.62}]}',
            "Field constraints:",
            "- `start_time` and `end_time` are numbers in seconds.",
            "- `end_time` must be greater than `start_time`.",
            "- `importance` must be a number from 0 to 1.",
            "- Do not include any extra keys.",
            "",
            format_utterance_timeline(utterances),
        ]
    )


def _frame_extraction_to_dict(result: FrameExtractionResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, FrameExtractionResult):
        return {
            "backend": result.backend,
            "frame_count": result.frame_count,
            "fallback_reason": result.fallback_reason,
        }
    return dict(result)


class StoryChapterMultimodalPipeline:
    def __init__(
        self,
        *,
        llm_client: MultimodalLlmClientProtocol,
        extract_frames: ExtractFrames = extract_frames_at_timestamps,
        frame_work_dir: Path | None = None,
        frame_max_height: int = 512,
        frame_interval_seconds: float = 1.0,
        max_frames: int | None = 120,
        max_output_tokens: int = 3200,
    ) -> None:
        self.llm_client = llm_client
        self.extract_frames = extract_frames
        self.frame_work_dir = frame_work_dir
        self.frame_max_height = frame_max_height
        self.frame_interval_seconds = frame_interval_seconds
        self.max_frames = max_frames
        self.max_output_tokens = max_output_tokens

    def run(
        self,
        *,
        video_id: str,
        video_path: Path,
        video_metadata: dict[str, Any],
        transcription_path: Path,
        output_root: Path,
    ) -> Path:
        video_duration_seconds = _video_duration_from_metadata(video_metadata)
        utterances = load_utterances_from_transcription(transcription_path)
        frame_timestamps_seconds = build_frame_timestamps(
            video_duration_seconds,
            frame_interval_seconds=self.frame_interval_seconds,
            max_frames=self.max_frames,
        )
        warnings: list[str] = []
        story_chapters: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            frame_dir = self.frame_work_dir or Path(tmpdir) / "frames"
            extraction_result = self.extract_frames(
                video_path=video_path,
                output_dir=frame_dir,
                timestamps_seconds=frame_timestamps_seconds,
                max_height=self.frame_max_height,
            )
            image_paths = sorted(frame_dir.glob("*.png"))

            if not utterances:
                warnings.append("No valid utterances found in transcription.")
            elif not image_paths:
                warnings.append("No frames extracted from video.")
            else:
                raw = self.llm_client.generate_json_multimodal(
                    system_prompt=build_multimodal_system_prompt(),
                    user_prompt=build_multimodal_user_prompt(
                        video_id=video_id,
                        video_duration_seconds=video_duration_seconds,
                        utterances=utterances,
                        frame_timestamps_seconds=frame_timestamps_seconds,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=frame_timestamps_seconds,
                    max_tokens=self.max_output_tokens,
                )
                drafts, parse_warnings = parse_chapter_drafts(raw)
                warnings.extend(parse_warnings)
                for draft in drafts:
                    story_chapters.append(
                        {
                            "start_time": float(draft["start_time"]),
                            "end_time": float(draft["end_time"]),
                            "title": str(draft["title"]),
                            "summary": str(draft["summary"]),
                            "importance": float(draft["importance"]),
                        }
                    )

            frame_extraction = _frame_extraction_to_dict(extraction_result)

        story_chapters.sort(key=lambda chapter: float(chapter["start_time"]))
        for index, chapter in enumerate(story_chapters, start=1):
            chapter["chapter_id"] = f"ch_{video_id}_{index:03d}"
            chapter["video_id"] = video_id

        output_dir = output_root / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "story_chapters.json"
        payload = {
            "video_id": video_id,
            "created_at": _now_iso(),
            "generation_mode": "multimodal_1fps",
            "video_path": str(video_path),
            "video_metadata": {"duration_seconds": video_duration_seconds},
            "source": {
                "transcription_path": str(transcription_path),
            },
            "frame_timestamps_seconds": frame_timestamps_seconds,
            "frame_extraction": frame_extraction,
            "utterances": [asdict(utterance) for utterance in utterances],
            "story_chapters": story_chapters,
            "warnings": warnings,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

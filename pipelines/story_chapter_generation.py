from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Protocol, Sequence


class TextLlmClientProtocol(Protocol):
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
class Utterance:
    utterance_id: str
    start_time: float
    end_time: float
    text: str
    speaker_id: str | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def load_utterances_from_transcription(path: Path) -> list[Utterance]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_response = payload.get("raw_response") if isinstance(payload, dict) else None
    chunks = raw_response.get("chunks", []) if isinstance(raw_response, dict) else []
    utterances: list[Utterance] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        offset_seconds = float(chunk.get("offset_seconds") or 0.0)
        raw_result = chunk.get("raw_result") or {}
        transcripts = raw_result.get("transcripts", []) if isinstance(raw_result, dict) else []
        for transcript in transcripts:
            if not isinstance(transcript, dict):
                continue
            sentences = transcript.get("sentences") or []
            for sentence in sentences:
                if not isinstance(sentence, dict):
                    continue
                text = str(sentence.get("text") or "").strip()
                if not text:
                    continue
                start = offset_seconds + float(sentence.get("begin_time") or 0.0) / 1000.0
                end = offset_seconds + float(sentence.get("end_time") or 0.0) / 1000.0
                if end <= start:
                    continue
                utterances.append(
                    Utterance(
                        utterance_id=f"u_{len(utterances) + 1:03d}",
                        start_time=_round_time(start),
                        end_time=_round_time(end),
                        text=text,
                        speaker_id=str(sentence["speaker_id"]) if "speaker_id" in sentence else None,
                    )
                )
    return utterances


def load_scenes(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenes = payload.get("scenes", []) if isinstance(payload, dict) else []
    normalized: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        try:
            start_time = float(scene["start_time"])
            end_time = float(scene["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_time <= start_time:
            continue
        normalized.append(
            {
                "scene_id": str(scene.get("scene_id") or f"s_{index:03d}"),
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "index": int(scene.get("index") or index),
                "clip_path": scene.get("clip_path"),
            }
        )
    return normalized


def format_utterance_timeline(utterances: Sequence[Utterance]) -> str:
    lines = ["UTTERANCES:"]
    for utterance in utterances:
        speaker = f" speaker={utterance.speaker_id}" if utterance.speaker_id is not None else ""
        lines.append(
            f"- {utterance.utterance_id} [{utterance.start_time:.3f}-{utterance.end_time:.3f}]{speaker}: {utterance.text}"
        )
    return "\n".join(lines)


def build_system_prompt() -> str:
    return (
        "You are a story structure analyst for short-drama timeline navigation. "
        "Your job is to identify story chapters. "
        "Use only the timestamped utterances provided by the user. "
        "Return valid JSON only, with no markdown or explanatory text."
    )


def _video_duration_from_metadata(video_metadata: dict[str, Any]) -> float:
    try:
        duration = float(video_metadata["duration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("video_metadata.duration_seconds is required for story chapter generation.") from exc
    if duration <= 0:
        raise ValueError("video_metadata.duration_seconds must be greater than 0.")
    return _round_time(duration)


def build_user_prompt(video_id: str, video_duration_seconds: float, utterances: Sequence[Utterance]) -> str:
    return "\n".join(
        [
            "## TASK",
            "Split the full short-drama video timeline into continuous story chapters for player navigation.",
            "A story chapter is a coherent narrative segment that helps a viewer understand what this part of the episode is about.",
            "The result will be shown as navigation labels on a video progress bar, so each chapter should be useful for locating plot progress.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {_round_time(video_duration_seconds):.3f}",
            "You will receive the video duration and a timestamped utterance timeline.",
            "Each utterance line contains an utterance id, start/end time in seconds, optional speaker id, and subtitle text.",
            "There are no video frames in this request. Use the subtitle timeline to infer chapter split points, titles, and summaries.",
            "",
            "## RULES",
            "- Use only information directly supported by the utterances.",
            "- Chapters must represent narrative progress, such as setup, conflict development, relationship change, reveal, reversal, decision, or ending beat.",
            "- Do not output interaction triggers, highlight moments, poll options, danmaku, audience emotions, or user feedback opportunities.",
            "- Do not split a chapter just because a single line sounds dramatic; prefer coherent multi-utterance story segments.",
            "- Do not force a fixed number of chapters. Use as many chapters as needed to represent the episode's story progression.",
            "- Chapters should be ordered by time and cover the full video timeline from 0.0 to VIDEO_DURATION_SECONDS.",
            "- Do not leave gaps between adjacent chapters. The `end_time` of one chapter should match the `start_time` of the next chapter.",
            "- Overlap is not allowed.",
            "- Treat chapter ranges as left-closed and right-open: [start_time, end_time), except the final chapter ends at VIDEO_DURATION_SECONDS.",
            "- If a boundary is at time `t`, the utterance starting at `t` belongs to the next chapter that starts at `t`, not the previous chapter.",
            "- The first chapter must start at 0.0.",
            "- The last chapter must end at VIDEO_DURATION_SECONDS.",
            "- Use subtitle content to choose meaningful internal split points. If a video segment has no subtitles, include it in the nearest appropriate chapter based on surrounding story context.",
            "- `title` should sound like a natural short-drama timeline label, not a story-analysis category.",
            "- Avoid abstract structural titles such as 开局设定、冲突升级、关系变化、反转揭露、高潮收束.",
            "- Prefer concrete plot labels grounded in characters, actions, objects, places, or visible story situations.",
            "- `title` should be short Chinese, preferably 4 to 8 Chinese characters.",
            "- `summary` should be one concise factual Chinese sentence grounded in the subtitles.",
            "- `importance` should reflect how important the chapter is for understanding the episode, from 0.0 to 1.0.",
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `chapters`.",
            "Each chapter object must contain exactly these keys: `start_time`, `end_time`, `title`, `summary`, `importance`.",
            "Output shape:",
            '{"chapters":[{"start_time":0.0,"end_time":18.4,"title":"债主堵门","summary":"女主醒来发现处境异常，故事冲突开始铺垫。","importance":0.62}]}',
            "Field constraints:",
            "- `start_time` and `end_time` are numbers in seconds.",
            "- `end_time` must be greater than `start_time`.",
            "- `importance` must be a number from 0 to 1.",
            "- Do not include any extra keys.",
            "",
            format_utterance_timeline(utterances),
        ]
    )


def parse_chapter_drafts(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("chapters"), list):
        return [], ["LLM response does not contain a chapters array."]

    drafts: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw["chapters"], start=1):
        if not isinstance(item, dict):
            warnings.append(f"Chapter #{index} is not an object.")
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            importance = float(item["importance"])
        except (KeyError, TypeError, ValueError):
            warnings.append(f"Chapter #{index} has invalid numeric fields.")
            continue

        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if end_time <= start_time:
            warnings.append(f"Chapter #{index} has end_time <= start_time.")
            continue
        if not title:
            warnings.append(f"Chapter #{index} has an empty title.")
            continue
        if not summary:
            warnings.append(f"Chapter #{index} has an empty summary.")
            continue
        if not 0.0 <= importance <= 1.0:
            warnings.append(f"Chapter #{index} has importance outside 0..1.")
            continue

        drafts.append(
            {
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "title": title,
                "summary": summary,
                "importance": importance,
                "source_rank": index,
            }
        )
    return drafts, warnings


def _containing_scene_for_start(time_sec: float, scenes: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in scenes:
        start_time = float(scene["start_time"])
        end_time = float(scene["end_time"])
        if start_time <= time_sec < end_time:
            return scene
    if scenes and time_sec == float(scenes[-1]["end_time"]):
        return scenes[-1]
    return None


def _containing_scene_for_end(time_sec: float, scenes: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in scenes:
        start_time = float(scene["start_time"])
        end_time = float(scene["end_time"])
        if start_time < time_sec <= end_time:
            return scene
    if scenes and time_sec == float(scenes[0]["start_time"]):
        return scenes[0]
    return None


def _nearest_scene_boundary(time_sec: float, scenes: Sequence[dict[str, Any]]) -> float:
    boundaries: list[float] = []
    for scene in scenes:
        boundaries.append(float(scene["start_time"]))
        boundaries.append(float(scene["end_time"]))
    return _round_time(min(boundaries, key=lambda boundary: abs(boundary - time_sec)))


def _snap_start_time(time_sec: float, scenes: Sequence[dict[str, Any]]) -> float:
    scene = _containing_scene_for_start(time_sec, scenes)
    if scene is not None:
        return _round_time(float(scene["start_time"]))
    return _nearest_scene_boundary(time_sec, scenes)


def _snap_end_time(time_sec: float, scenes: Sequence[dict[str, Any]]) -> float:
    scene = _containing_scene_for_end(time_sec, scenes)
    if scene is not None:
        return _round_time(float(scene["end_time"]))
    return _nearest_scene_boundary(time_sec, scenes)


def snap_chapter_to_scenes(
    draft: dict[str, Any],
    scenes: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    if scenes:
        start_time = _snap_start_time(float(draft["start_time"]), scenes)
        end_time = _snap_end_time(float(draft["end_time"]), scenes)
    else:
        start_time = _round_time(float(draft["start_time"]))
        end_time = _round_time(float(draft["end_time"]))

    if end_time <= start_time:
        return None

    return {
        "start_time": start_time,
        "end_time": end_time,
        "title": str(draft["title"]),
        "summary": str(draft["summary"]),
        "importance": float(draft["importance"]),
    }


class StoryChapterPipeline:
    def __init__(
        self,
        *,
        llm_client: TextLlmClientProtocol,
        max_output_tokens: int = 2400,
    ) -> None:
        self.llm_client = llm_client
        self.max_output_tokens = max_output_tokens

    def run(
        self,
        *,
        video_id: str,
        video_metadata: dict[str, Any],
        transcription_path: Path,
        scene_detection_path: Path,
        output_root: Path,
    ) -> Path:
        utterances = load_utterances_from_transcription(transcription_path)
        scenes = load_scenes(scene_detection_path)
        video_duration_seconds = _video_duration_from_metadata(video_metadata)
        warnings: list[str] = []

        story_chapters: list[dict[str, Any]] = []
        if not utterances:
            warnings.append("No valid utterances found in transcription.")
        else:
            raw = self.llm_client.generate_json_multimodal(
                system_prompt=build_system_prompt(),
                user_prompt=build_user_prompt(video_id, video_duration_seconds, utterances),
                max_tokens=self.max_output_tokens,
            )
            drafts, parse_warnings = parse_chapter_drafts(raw)
            warnings.extend(parse_warnings)

            for draft in drafts:
                # Scene-boundary snapping is intentionally disabled for now.
                # Story chapters are full-timeline semantic segments; snapping each
                # chapter start/end independently can introduce overlaps or gaps.
                story_chapters.append(
                    {
                        "start_time": float(draft["start_time"]),
                        "end_time": float(draft["end_time"]),
                        "title": str(draft["title"]),
                        "summary": str(draft["summary"]),
                        "importance": float(draft["importance"]),
                    }
                )

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
            "video_metadata": {"duration_seconds": video_duration_seconds},
            "source": {
                "transcription_path": str(transcription_path),
                "scene_detection_path": str(scene_detection_path),
            },
            "utterances": [asdict(utterance) for utterance in utterances],
            "scenes": list(scenes),
            "story_chapters": story_chapters,
            "warnings": warnings,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

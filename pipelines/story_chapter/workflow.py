from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
from typing import Any, Protocol, Sequence

from pipelines.story_chapter.baseline_text import Utterance, _round_time, load_scenes, load_utterances_from_transcription
from pipelines.utils import FrameExtractionResult, extract_frames_at_timestamps


@dataclass(frozen=True)
class BoundaryCandidate:
    candidate_id: str
    time: float
    rule_score: float
    score: float
    signals: list[str]
    evidence: dict[str, Any]
    topic_shift_score: float | None = None
    topic_shift_reason: str | None = None


class StoryChapterLlmClientProtocol(Protocol):
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
class ChapterSelectionConstraints:
    min_chapter_seconds: float = 12.0
    target_chapter_seconds: float = 35.0
    max_chapter_seconds: float = 75.0
    max_chapters: int = 8


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _scene_boundaries(scenes: Sequence[dict[str, Any]], video_duration_seconds: float) -> list[float]:
    boundaries: list[float] = []
    for scene in scenes:
        try:
            start_time = float(scene["start_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 < start_time < video_duration_seconds:
            boundaries.append(_round_time(start_time))
    return sorted(set(boundaries))


def _nearest_boundary(time_sec: float, boundaries: Sequence[float], max_distance_seconds: float) -> float | None:
    if not boundaries:
        return None
    nearest = min(boundaries, key=lambda boundary: abs(boundary - time_sec))
    if abs(nearest - time_sec) <= max_distance_seconds:
        return _round_time(nearest)
    return None


def _text_density(utterances: Sequence[Utterance], *, start_time: float, end_time: float) -> float:
    if end_time <= start_time:
        return 0.0
    char_count = 0
    for utterance in utterances:
        if utterance.end_time <= start_time or utterance.start_time >= end_time:
            continue
        char_count += len("".join(utterance.text.split()))
    return char_count / (end_time - start_time)


def _raw_candidate(
    *,
    time: float,
    signal: str,
    score: float,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "time": _round_time(time),
        "signals": [signal],
        "rule_score": _clamp_score(score),
        "evidence": dict(evidence),
    }


def _merge_raw_candidates(raw_candidates: list[dict[str, Any]], merge_window_seconds: float) -> list[BoundaryCandidate]:
    raw_candidates.sort(key=lambda candidate: (float(candidate["time"]), -float(candidate["rule_score"])))
    clusters: list[list[dict[str, Any]]] = []
    for candidate in raw_candidates:
        if not clusters:
            clusters.append([candidate])
            continue
        previous_time = float(clusters[-1][-1]["time"])
        if abs(float(candidate["time"]) - previous_time) <= merge_window_seconds:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])

    merged: list[BoundaryCandidate] = []
    for index, cluster in enumerate(clusters, start=1):
        chosen = max(
            cluster,
            key=lambda item: (
                "scene_boundary" in item["signals"],
                float(item["rule_score"]),
                -abs(float(item["time"]) - float(cluster[0]["time"])),
            ),
        )
        signals: list[str] = []
        evidence: dict[str, Any] = {}
        score = 0.0
        for item in cluster:
            score = max(score, float(item["rule_score"]))
            for signal in item["signals"]:
                if signal not in signals:
                    signals.append(signal)
            evidence.update(item["evidence"])
        if len(signals) > 1:
            score += 0.12 * (len(signals) - 1)
        rule_score = _clamp_score(score)
        merged.append(
            BoundaryCandidate(
                candidate_id=f"bc_{index:03d}",
                time=_round_time(float(chosen["time"])),
                rule_score=rule_score,
                score=rule_score,
                signals=signals,
                evidence=evidence,
            )
        )
    return merged


def recall_boundary_candidates(
    *,
    utterances: Sequence[Utterance],
    scenes: Sequence[dict[str, Any]],
    video_duration_seconds: float,
    pause_threshold_seconds: float = 1.2,
    density_window_seconds: float = 12.0,
    merge_window_seconds: float = 3.0,
) -> list[BoundaryCandidate]:
    boundaries = _scene_boundaries(scenes, video_duration_seconds)
    raw_candidates: list[dict[str, Any]] = []

    for boundary in boundaries:
        raw_candidates.append(
            _raw_candidate(
                time=boundary,
                signal="scene_boundary",
                score=0.28,
                evidence={"scene_boundary_time": boundary},
            )
        )

    for previous, current in zip(utterances, utterances[1:]):
        gap = _round_time(current.start_time - previous.end_time)
        if gap < pause_threshold_seconds:
            continue
        candidate_time = current.start_time
        snapped = _nearest_boundary(candidate_time, boundaries, max_distance_seconds=merge_window_seconds)
        pause_score = 0.35 + min(0.35, gap / 8.0)
        raw_candidates.append(
            _raw_candidate(
                time=snapped if snapped is not None else candidate_time,
                signal="long_pause",
                score=pause_score,
                evidence={"gap_seconds": gap},
            )
        )

    for boundary in boundaries:
        before_density = _text_density(
            utterances,
            start_time=max(0.0, boundary - density_window_seconds),
            end_time=boundary,
        )
        after_density = _text_density(
            utterances,
            start_time=boundary,
            end_time=min(video_duration_seconds, boundary + density_window_seconds),
        )
        density_delta = abs(after_density - before_density)
        if density_delta < 1.0:
            continue
        density_score = min(0.55, density_delta / 12.0)
        raw_candidates.append(
            _raw_candidate(
                time=boundary,
                signal="dialogue_density_change",
                score=density_score,
                evidence={
                    "before_density": round(before_density, 3),
                    "after_density": round(after_density, 3),
                    "density_delta": round(density_delta, 3),
                },
            )
        )

    return _merge_raw_candidates(raw_candidates, merge_window_seconds)


def _format_utterance_line(utterance: Utterance) -> str:
    return f"{utterance.utterance_id} [{utterance.start_time:.3f}-{utterance.end_time:.3f}]: {utterance.text}"


def _context_utterances(
    utterances: Sequence[Utterance],
    *,
    time_sec: float,
    before_count: int,
    after_count: int,
) -> tuple[list[Utterance], list[Utterance]]:
    before = [utterance for utterance in utterances if utterance.end_time <= time_sec]
    after = [utterance for utterance in utterances if utterance.start_time >= time_sec]
    return before[-before_count:], after[:after_count]


def build_topic_shift_system_prompt() -> str:
    return (
        "You are a short-drama story boundary reviewer. "
        "Score whether each candidate boundary separates two different story chapters. "
        "Return valid JSON only."
    )


def build_topic_shift_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    candidates: Sequence[BoundaryCandidate],
    context_utterance_count: int = 8,
) -> str:
    lines = [
        "## TASK",
        "Score topic shift strength for candidate story chapter boundaries.",
        "Use only the subtitle context around each candidate.",
        "",
        "## INPUT",
        f"VIDEO_ID: {video_id}",
        f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
        "",
        "## OUTPUT",
        "Return JSON only with this shape:",
        '{"topic_shift_reviews":[{"candidate_id":"bc_001","topic_shift_score":0.82,"reason":"前后剧情目标发生变化。"}]}',
        "Rules:",
        "- topic_shift_score must be a number from 0 to 1.",
        "- 0 means the candidate is inside the same story beat.",
        "- 1 means the candidate clearly starts a new story chapter.",
        "- Do not invent candidate ids.",
        "",
        "## CANDIDATES",
    ]
    for candidate in candidates:
        before, after = _context_utterances(
            utterances,
            time_sec=candidate.time,
            before_count=context_utterance_count,
            after_count=context_utterance_count,
        )
        lines.extend(
            [
                f"CANDIDATE_ID: {candidate.candidate_id}",
                f"TIME: {candidate.time:.3f}",
                f"SIGNALS: {', '.join(candidate.signals)}",
                "BEFORE:",
                *(_format_utterance_line(utterance) for utterance in before),
                "AFTER:",
                *(_format_utterance_line(utterance) for utterance in after),
                "",
            ]
        )
    return "\n".join(lines)


def parse_topic_shift_reviews(raw: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("topic_shift_reviews"), list):
        return {}, ["LLM response does not contain topic_shift_reviews array."]
    reviews: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for index, item in enumerate(raw["topic_shift_reviews"], start=1):
        if not isinstance(item, dict):
            warnings.append(f"Topic shift review #{index} is not an object.")
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id:
            warnings.append(f"Topic shift review #{index} has empty candidate_id.")
            continue
        try:
            score = float(item["topic_shift_score"])
        except (KeyError, TypeError, ValueError):
            warnings.append(f"Topic shift review #{index} has invalid topic_shift_score.")
            continue
        reviews[candidate_id] = {
            "topic_shift_score": _clamp_score(score),
            "reason": str(item.get("reason") or "").strip(),
        }
    return reviews, warnings


def score_topic_shifts_with_llm(
    *,
    llm_client: StoryChapterLlmClientProtocol,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    candidates: Sequence[BoundaryCandidate],
    context_utterance_count: int = 8,
    max_tokens: int = 2400,
) -> tuple[list[BoundaryCandidate], list[str], dict[str, Any]]:
    if not candidates:
        return [], [], {"topic_shift_reviews": []}
    raw = llm_client.generate_json_multimodal(
        system_prompt=build_topic_shift_system_prompt(),
        user_prompt=build_topic_shift_user_prompt(
            video_id=video_id,
            video_duration_seconds=video_duration_seconds,
            utterances=utterances,
            candidates=candidates,
            context_utterance_count=context_utterance_count,
        ),
        max_tokens=max_tokens,
    )
    reviews, warnings = parse_topic_shift_reviews(raw)
    scored: list[BoundaryCandidate] = []
    for candidate in candidates:
        review = reviews.get(candidate.candidate_id)
        if review is None:
            scored.append(candidate)
            continue
        topic_score = float(review["topic_shift_score"])
        final_score = _clamp_score(0.70 * candidate.rule_score + 0.30 * topic_score)
        signals = list(candidate.signals)
        if "llm_topic_shift" not in signals:
            signals.append("llm_topic_shift")
        scored.append(
            replace(
                candidate,
                score=final_score,
                topic_shift_score=topic_score,
                topic_shift_reason=str(review.get("reason") or ""),
                signals=signals,
            )
        )
    return scored, warnings, raw


def build_selector_system_prompt() -> str:
    return (
        "You are a multimodal short-drama story chapter selector. "
        "Select final chapter boundaries only from the provided boundary candidates. "
        "Use full subtitles for global story context and candidate-local frames for visual evidence. "
        "Return valid JSON only."
    )


def build_selector_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    candidates: Sequence[BoundaryCandidate],
    frame_timestamps_by_candidate: dict[str, list[float]],
    constraints: ChapterSelectionConstraints,
) -> str:
    lines = [
        "## TASK",
        "Select final continuous story chapters for player timeline navigation.",
        "You must use full subtitles for global story context.",
        "Internal chapter boundaries must be selected from BOUNDARY_CANDIDATES only.",
        "",
        "## VIDEO",
        f"VIDEO_ID: {video_id}",
        f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
        "",
        "## CONSTRAINTS",
        f"MIN_CHAPTER_SECONDS: {constraints.min_chapter_seconds:.3f}",
        f"TARGET_CHAPTER_SECONDS: {constraints.target_chapter_seconds:.3f}",
        f"MAX_CHAPTER_SECONDS: {constraints.max_chapter_seconds:.3f}",
        f"MAX_CHAPTERS: {constraints.max_chapters}",
        "",
        "## FULL_UTTERANCE_TIMELINE",
        *(_format_utterance_line(utterance) for utterance in utterances),
        "",
        "## BOUNDARY_CANDIDATES",
    ]
    for candidate in candidates:
        frame_times = ", ".join(f"{time:.3f}" for time in frame_timestamps_by_candidate.get(candidate.candidate_id, []))
        lines.extend(
            [
                f"CANDIDATE_ID: {candidate.candidate_id}",
                f"TIME: {candidate.time:.3f}",
                f"SCORE: {candidate.score:.3f}",
                f"SIGNALS: {', '.join(candidate.signals)}",
                f"TOPIC_SHIFT_REASON: {candidate.topic_shift_reason or ''}",
                f"FRAME_TIMESTAMPS_SECONDS: {frame_times}",
                "",
            ]
        )
    lines.extend(
        [
            "## OUTPUT",
            "Return JSON only with keys: chapters, rejected_candidates, warnings.",
            "Each chapter must contain start_time, end_time, end_boundary_candidate_id, title, summary, importance.",
            "The first chapter must start at 0.0. The final chapter must end at VIDEO_DURATION_SECONDS.",
            "Do not create chapters shorter than MIN_CHAPTER_SECONDS unless the whole video is shorter than that.",
            "Prefer 3 to 6 chapters for a normal short-drama episode; use fewer only when the story is very simple.",
            "importance must be a number from 0 to 1. Do not use labels such as high, medium, or low.",
            "title should be short Chinese, preferably 4 to 10 Chinese characters, and suitable for a video timeline.",
            "summary should be one concise factual Chinese sentence.",
        ]
    )
    return "\n".join(lines)


def _candidate_time_by_id(candidates: Sequence[BoundaryCandidate]) -> dict[str, float]:
    return {candidate.candidate_id: candidate.time for candidate in candidates}


def _same_time(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 0.01


def _chapter_from_raw(
    *,
    raw_chapter: dict[str, Any],
    video_id: str,
    index: int,
) -> dict[str, Any] | None:
    try:
        start_time = _round_time(float(raw_chapter["start_time"]))
        end_time = _round_time(float(raw_chapter["end_time"]))
    except (KeyError, TypeError, ValueError):
        return None
    importance_raw = raw_chapter.get("importance")
    if isinstance(importance_raw, str):
        importance = {
            "high": 0.85,
            "medium": 0.6,
            "low": 0.35,
            "重要": 0.85,
            "中等": 0.6,
            "较低": 0.35,
        }.get(importance_raw.strip().lower())
        if importance is None:
            try:
                importance = _clamp_score(float(importance_raw))
            except ValueError:
                return None
    else:
        try:
            importance = _clamp_score(float(importance_raw))
        except (TypeError, ValueError):
            return None
    title = str(raw_chapter.get("title") or "").strip()
    summary = str(raw_chapter.get("summary") or "").strip()
    if not title or not summary or end_time <= start_time:
        return None
    boundary_id = raw_chapter.get("end_boundary_candidate_id")
    return {
        "chapter_id": f"ch_{video_id}_{index:03d}",
        "video_id": video_id,
        "start_time": start_time,
        "end_time": end_time,
        "end_boundary_candidate_id": str(boundary_id) if boundary_id is not None else None,
        "title": title,
        "summary": summary,
        "importance": importance,
    }


def parse_and_validate_selector_result(
    *,
    raw: dict[str, Any],
    video_id: str,
    video_duration_seconds: float,
    candidates: Sequence[BoundaryCandidate],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("chapters"), list):
        return [], ["MLLM selector response does not contain a chapters array."]
    candidate_times = _candidate_time_by_id(candidates)
    chapters: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, raw_chapter in enumerate(raw["chapters"], start=1):
        if not isinstance(raw_chapter, dict):
            warnings.append(f"Chapter #{index} is not an object.")
            continue
        chapter = _chapter_from_raw(raw_chapter=raw_chapter, video_id=video_id, index=index)
        if chapter is None:
            warnings.append(f"Chapter #{index} has invalid fields.")
            continue
        chapters.append(chapter)

    if not chapters:
        return [], warnings or ["No valid chapters returned by MLLM selector."]

    chapters.sort(key=lambda chapter: float(chapter["start_time"]))
    if not _same_time(float(chapters[0]["start_time"]), 0.0):
        warnings.append("First chapter does not start at 0.0.")
    if not _same_time(float(chapters[-1]["end_time"]), video_duration_seconds):
        chapters[-1]["end_time"] = _round_time(video_duration_seconds)
        warnings.append("Adjusted final chapter end_time to video duration.")

    for index, chapter in enumerate(chapters):
        if index > 0:
            previous = chapters[index - 1]
            if not _same_time(float(previous["end_time"]), float(chapter["start_time"])):
                warnings.append(f"Chapter #{index + 1} is not continuous with previous chapter.")
        boundary_id = chapter["end_boundary_candidate_id"]
        is_final = index == len(chapters) - 1
        if is_final:
            continue
        if not boundary_id or boundary_id not in candidate_times:
            warnings.append(f"Chapter #{index + 1} end boundary is not from candidates.")
            continue
        if not _same_time(float(chapter["end_time"]), candidate_times[boundary_id]):
            warnings.append(f"Chapter #{index + 1} end_time does not match its candidate boundary.")

    if warnings:
        return [], warnings
    for index, chapter in enumerate(chapters, start=1):
        chapter["chapter_id"] = f"ch_{video_id}_{index:03d}"
    return chapters, []


def build_fallback_chapters(
    *,
    video_id: str,
    video_duration_seconds: float,
    candidates: Sequence[BoundaryCandidate],
    constraints: ChapterSelectionConstraints,
) -> list[dict[str, Any]]:
    selected_times: list[float] = []
    last_time = 0.0
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        if len(selected_times) >= max(0, constraints.max_chapters - 1):
            break
        if candidate.time - last_time < constraints.min_chapter_seconds:
            continue
        if video_duration_seconds - candidate.time < constraints.min_chapter_seconds:
            continue
        selected_times.append(candidate.time)
        last_time = candidate.time
    boundaries = [0.0, *sorted(selected_times), _round_time(video_duration_seconds)]
    chapters: list[dict[str, Any]] = []
    for index, (start_time, end_time) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        chapters.append(
            {
                "chapter_id": f"ch_{video_id}_{index:03d}",
                "video_id": video_id,
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "end_boundary_candidate_id": None,
                "title": f"剧情片段{index}",
                "summary": "该片段为自动兜底生成，需人工复核。",
                "importance": 0.3,
            }
        )
    return chapters


def _video_duration_from_metadata(video_metadata: dict[str, Any]) -> float:
    try:
        duration = float(video_metadata["duration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("video_metadata.duration_seconds is required for story chapter workflow.") from exc
    if duration <= 0:
        raise ValueError("video_metadata.duration_seconds must be greater than 0.")
    return _round_time(duration)


def _candidate_to_dict(candidate: BoundaryCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "time": candidate.time,
        "rule_score": candidate.rule_score,
        "score": candidate.score,
        "signals": list(candidate.signals),
        "evidence": dict(candidate.evidence),
        "topic_shift_score": candidate.topic_shift_score,
        "topic_shift_reason": candidate.topic_shift_reason,
    }


def _frame_extraction_to_dict(result: FrameExtractionResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, FrameExtractionResult):
        return {
            "backend": result.backend,
            "frame_count": result.frame_count,
            "fallback_reason": result.fallback_reason,
        }
    return dict(result)


def _selector_frame_timestamps(
    *,
    candidates: Sequence[BoundaryCandidate],
    video_duration_seconds: float,
    offsets_seconds: Sequence[float],
) -> tuple[list[float], dict[str, list[float]]]:
    all_timestamps: list[float] = []
    by_candidate: dict[str, list[float]] = {}
    for candidate in candidates:
        timestamps = [
            _round_time(min(video_duration_seconds, max(0.0, candidate.time + offset)))
            for offset in offsets_seconds
        ]
        timestamps = sorted(set(timestamps))
        by_candidate[candidate.candidate_id] = timestamps
        all_timestamps.extend(timestamps)
    return sorted(set(all_timestamps)), by_candidate


class StoryChapterWorkflowPipeline:
    def __init__(
        self,
        *,
        text_llm_client: StoryChapterLlmClientProtocol,
        mllm_client: StoryChapterLlmClientProtocol,
        extract_frames=extract_frames_at_timestamps,
        top_candidates: int = 16,
        candidate_frame_offsets_seconds: Sequence[float] = (-1.0, 0.0, 1.0),
        frame_max_height: int = 512,
        constraints: ChapterSelectionConstraints | None = None,
        text_max_tokens: int = 2400,
        selector_max_tokens: int = 3600,
    ) -> None:
        self.text_llm_client = text_llm_client
        self.mllm_client = mllm_client
        self.extract_frames = extract_frames
        self.top_candidates = top_candidates
        self.candidate_frame_offsets_seconds = tuple(candidate_frame_offsets_seconds)
        self.frame_max_height = frame_max_height
        self.constraints = constraints or ChapterSelectionConstraints()
        self.text_max_tokens = text_max_tokens
        self.selector_max_tokens = selector_max_tokens

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
        video_duration_seconds = _video_duration_from_metadata(video_metadata)
        utterances = load_utterances_from_transcription(transcription_path)
        scenes = load_scenes(scene_detection_path)
        warnings: list[str] = []

        candidates = recall_boundary_candidates(
            utterances=utterances,
            scenes=scenes,
            video_duration_seconds=video_duration_seconds,
        )
        scored_candidates, topic_warnings, topic_raw = score_topic_shifts_with_llm(
            llm_client=self.text_llm_client,
            video_id=video_id,
            video_duration_seconds=video_duration_seconds,
            utterances=utterances,
            candidates=candidates,
            max_tokens=self.text_max_tokens,
        )
        warnings.extend(topic_warnings)
        selected_candidates = sorted(scored_candidates, key=lambda candidate: candidate.score, reverse=True)[
            : self.top_candidates
        ]
        selected_candidates = sorted(selected_candidates, key=lambda candidate: candidate.time)
        frame_timestamps, frame_timestamps_by_candidate = _selector_frame_timestamps(
            candidates=selected_candidates,
            video_duration_seconds=video_duration_seconds,
            offsets_seconds=self.candidate_frame_offsets_seconds,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            frame_dir = Path(tmpdir) / "selector_frames"
            extraction_result = self.extract_frames(
                video_path=video_path,
                output_dir=frame_dir,
                timestamps_seconds=frame_timestamps,
                max_height=self.frame_max_height,
            )
            image_paths = sorted(frame_dir.glob("*.png"))
            selector_raw = self.mllm_client.generate_json_multimodal(
                system_prompt=build_selector_system_prompt(),
                user_prompt=build_selector_user_prompt(
                    video_id=video_id,
                    video_duration_seconds=video_duration_seconds,
                    utterances=utterances,
                    candidates=selected_candidates,
                    frame_timestamps_by_candidate=frame_timestamps_by_candidate,
                    constraints=self.constraints,
                ),
                image_paths=image_paths,
                frame_timestamps_seconds=frame_timestamps,
                max_tokens=self.selector_max_tokens,
            )
            frame_extraction = _frame_extraction_to_dict(extraction_result)

        story_chapters, selector_warnings = parse_and_validate_selector_result(
            raw=selector_raw,
            video_id=video_id,
            video_duration_seconds=video_duration_seconds,
            candidates=selected_candidates,
        )
        if selector_warnings:
            warnings.extend(selector_warnings)
            story_chapters = build_fallback_chapters(
                video_id=video_id,
                video_duration_seconds=video_duration_seconds,
                candidates=selected_candidates,
                constraints=self.constraints,
            )
            warnings.append("Used rule selector fallback because MLLM selector output was invalid.")

        output_dir = output_root / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "story_chapters.json"
        payload = {
            "video_id": video_id,
            "created_at": _now_iso(),
            "generation_mode": "workflow_candidate_mllm_selector",
            "video_path": str(video_path),
            "video_metadata": {"duration_seconds": video_duration_seconds},
            "source": {
                "transcription_path": str(transcription_path),
                "scene_detection_path": str(scene_detection_path),
            },
            "utterances": [asdict(utterance) for utterance in utterances],
            "scenes": list(scenes),
            "boundary_candidates": [_candidate_to_dict(candidate) for candidate in scored_candidates],
            "selected_boundary_candidates": [_candidate_to_dict(candidate) for candidate in selected_candidates],
            "topic_shift_result": topic_raw,
            "frame_timestamps_seconds": frame_timestamps,
            "frame_timestamps_by_candidate": frame_timestamps_by_candidate,
            "frame_extraction": frame_extraction,
            "mllm_selector_result": selector_raw,
            "story_chapters": story_chapters,
            "warnings": warnings,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path


__all__ = [
    "BoundaryCandidate",
    "ChapterSelectionConstraints",
    "StoryChapterWorkflowPipeline",
    "build_selector_system_prompt",
    "build_selector_user_prompt",
    "build_topic_shift_user_prompt",
    "build_fallback_chapters",
    "parse_and_validate_selector_result",
    "parse_topic_shift_reviews",
    "recall_boundary_candidates",
    "score_topic_shifts_with_llm",
]

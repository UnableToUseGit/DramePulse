from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from pipelines.client import LlmClientProtocol
from pipelines.utils import (
    SubtitleSegment,
    extract_frames_at_timestamps,
    format_subtitle_timeline,
    load_subtitle_segments,
)


def _build_system_prompt() -> str:
    return (
        "You are an interaction plan generation model for short drama highlights. "
        "Generate a low-friction danmaku poll for mobile viewing. Return only JSON."
    )


def _build_user_prompt(
    *,
    highlight_asset: dict[str, Any],
    subtitle_context: str,
    danmaku_items: list[Any],
    frame_timestamps: list[float],
) -> str:
    danmaku_text = _format_danmaku_context(danmaku_items)
    frame_hint = ", ".join(f"{timestamp:.3f}s" for timestamp in frame_timestamps) or "none"
    return "\n".join(
        [
            f"VIDEO_ID: {highlight_asset.get('video_id', '')}",
            "Task: generate one Interaction Plan for this short drama highlight.",
            "Constraints:",
            "- interaction_type must be danmaku_poll.",
            "- Generate 2 or 3 options.",
            "- Generate one poll question in `question`.",
            "- Option text should be short and suitable for mobile tap interaction.",
            "- danmaku_text should sound like a real danmaku expression.",
            "- Return JSON in this exact shape:",
            '{ "question": "...", "options": [{ "text": "...", "danmaku_text": "...", "base_score": 0.8 }], "feedback": { "resonance_text_template": "你和 {ratio}% 的观众一样选择了「{option}」" } }',
            "",
            "[HIGHLIGHT_ASSET]",
            str(highlight_asset),
            "[/HIGHLIGHT_ASSET]",
            "",
            f"FRAME_TIMESTAMPS: {frame_hint}",
            subtitle_context,
            "",
            "[DANMAKU_CONTEXT]",
            danmaku_text,
            "[/DANMAKU_CONTEXT]",
        ]
    )


def _format_danmaku_item(item: Any) -> str | None:
    if isinstance(item, str):
        text = _clean_text(item)
        return text or None
    if not isinstance(item, dict):
        return None

    text = _clean_text(item.get("text", ""))
    if not text:
        return None

    prefix = ""
    try:
        prefix = f"[{float(item['time_sec']):.3f}s] "
    except (KeyError, TypeError, ValueError):
        pass

    meta_parts: list[str] = []
    if "digg_count" in item:
        meta_parts.append(f"digg={item['digg_count']}")
    if "score" in item:
        meta_parts.append(f"score={item['score']}")
    meta = f" ({', '.join(meta_parts)})" if meta_parts else ""
    return f"{prefix}{text}{meta}"


def _format_danmaku_context(danmaku_items: list[Any]) -> str:
    lines: list[str] = []
    for item in danmaku_items:
        line = _format_danmaku_item(item)
        if line:
            lines.append(f"- {line}")
        if len(lines) >= 50:
            break
    return "\n".join(lines) or "- none"


def _subtitle_segments_in_window(
    segments: list[SubtitleSegment],
    *,
    start_time: float,
    end_time: float,
    before_sec: float,
    after_sec: float,
) -> list[SubtitleSegment]:
    window_start = max(0.0, start_time - before_sec)
    window_end = end_time + after_sec
    return [
        segment
        for segment in segments
        if segment.end >= window_start and segment.start <= window_end
    ]


def _frame_timestamps_for_highlight(highlight_asset: dict[str, Any]) -> list[float]:
    start_time = float(highlight_asset["start_time"])
    end_time = float(highlight_asset["end_time"])
    midpoint = start_time + (end_time - start_time) / 2.0
    timestamps = [max(0.0, start_time - 2.0), midpoint, end_time + 1.0]
    return sorted({round(timestamp, 3) for timestamp in timestamps})


def _fallback_template(highlight_type: str) -> tuple[str, list[tuple[str, str]]]:
    templates: dict[str, tuple[str, list[tuple[str, str]]]] = {
        "身份揭露": (
            "这波反转你怎么看？",
            [("卧槽反转了", "卧槽反转了！"), ("爽到了", "这波爽到了！")],
        ),
        "打脸反杀": (
            "这一幕爽不爽？",
            [("太争气了", "女主太争气了！"), ("爽到了", "这波爽到了！")],
        ),
        "甜蜜撒糖": (
            "这段什么感觉？",
            [("磕到了", "磕到了磕到了！"), ("有点甜", "这段有点甜！")],
        ),
        "冲突爆发": (
            "你站哪边？",
            [("站女主", "我站女主！"), ("站男主", "我站男主！")],
        ),
    }
    return templates.get(
        highlight_type,
        (
            "这段你怎么看？",
            [("有点上头", "这段有点上头！"), ("继续看", "继续看下去！")],
        ),
    )


def _clean_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _default_feedback(raw_feedback: Any) -> dict[str, Any]:
    template = "你和 {ratio}% 的观众一样选择了「{option}」"
    if isinstance(raw_feedback, dict):
        template = _clean_text(raw_feedback.get("resonance_text_template", template)) or template
    return {
        "type": "poll_result",
        "show_ratio": True,
        "show_resonance_text": True,
        "resonance_text_template": template,
    }


def _build_plan_from_question_and_options(
    *,
    highlight_asset: dict[str, Any],
    question: str,
    options: list[dict[str, Any]],
    feedback: dict[str, Any] | None = None,
    display_position: str = "subtitle_safe_area",
) -> dict[str, Any]:
    highlight_id = str(highlight_asset["highlight_id"])
    normalized_options: list[dict[str, Any]] = []
    for index, option in enumerate(options, start=1):
        text = _clean_text(option["text"])
        danmaku_text = _clean_text(option["danmaku_text"])
        item = {
            "option_id": f"o_{highlight_id}_{index:03d}",
            "text": text,
            "danmaku_text": danmaku_text,
            "rank": index,
            "base_score": float(option.get("base_score", max(0.1, 0.9 - index * 0.1))),
        }
        normalized_options.append(item)

    return {
        "interaction_id": f"i_{highlight_id}",
        "highlight_id": highlight_id,
        "video_id": str(highlight_asset["video_id"]),
        "trigger_time": float(highlight_asset["start_time"]),
        "expire_time": float(highlight_asset["end_time"]),
        "interaction_type": "danmaku_poll",
        "question": question,
        "options": normalized_options,
        "feedback": feedback or _default_feedback(None),
        "display_position": display_position,
        "status": "active",
    }


def _fallback_plan(
    *,
    highlight_asset: dict[str, Any],
    display_position: str = "subtitle_safe_area",
) -> dict[str, Any]:
    question, option_pairs = _fallback_template(str(highlight_asset.get("highlight_type", "")))
    options = [
        {"text": text, "danmaku_text": danmaku_text}
        for text, danmaku_text in option_pairs
    ]
    return _build_plan_from_question_and_options(
        highlight_asset=highlight_asset,
        question=question,
        options=options,
        feedback=_default_feedback(None),
        display_position=display_position,
    )


def _extract_raw_plan(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    nested = raw.get("interaction_plan")
    if isinstance(nested, dict):
        return nested
    return raw


def parse_interaction_plan(
    raw: Any,
    *,
    highlight_asset: dict[str, Any],
    display_position: str = "subtitle_safe_area",
) -> dict[str, Any]:
    raw_plan = _extract_raw_plan(raw)
    if raw_plan is None:
        return _fallback_plan(highlight_asset=highlight_asset, display_position=display_position)

    question = _clean_text(raw_plan.get("question", ""))
    raw_options = raw_plan.get("options", [])
    if not question or not isinstance(raw_options, list) or not 2 <= len(raw_options) <= 3:
        return _fallback_plan(highlight_asset=highlight_asset, display_position=display_position)

    options: list[dict[str, Any]] = []
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            return _fallback_plan(highlight_asset=highlight_asset, display_position=display_position)
        text = _clean_text(raw_option.get("text", ""))
        danmaku_text = _clean_text(raw_option.get("danmaku_text", ""))
        if not text or not danmaku_text:
            return _fallback_plan(highlight_asset=highlight_asset, display_position=display_position)
        options.append(
            {
                "text": text,
                "danmaku_text": danmaku_text,
                "base_score": raw_option.get("base_score", max(0.1, 0.9 - len(options) * 0.1)),
            }
        )

    return _build_plan_from_question_and_options(
        highlight_asset=highlight_asset,
        question=question,
        options=options,
        feedback=_default_feedback(raw_plan.get("feedback")),
        display_position=display_position,
    )


class InteractionPlanGenerationPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        subtitle_context_before_sec: float = 8.0,
        subtitle_context_after_sec: float = 5.0,
        max_output_tokens: int = 4800,
        display_position: str = "subtitle_safe_area",
    ) -> None:
        self.llm_client = llm_client
        self.subtitle_context_before_sec = subtitle_context_before_sec
        self.subtitle_context_after_sec = subtitle_context_after_sec
        self.max_output_tokens = max_output_tokens
        self.display_position = display_position

    def run(
        self,
        *,
        highlight_asset: dict[str, Any],
        video_file_path: Path,
        subtitle_file_path: Path,
        danmaku_items: list[Any],
    ) -> dict[str, Any]:
        start_time = float(highlight_asset["start_time"])
        end_time = float(highlight_asset["end_time"])
        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitle_context_segments = _subtitle_segments_in_window(
            subtitle_segments,
            start_time=start_time,
            end_time=end_time,
            before_sec=self.subtitle_context_before_sec,
            after_sec=self.subtitle_context_after_sec,
        )
        subtitle_context = format_subtitle_timeline(subtitle_context_segments)
        frame_timestamps = _frame_timestamps_for_highlight(highlight_asset)

        with tempfile.TemporaryDirectory(prefix=f"interaction_{highlight_asset['video_id']}_") as temp_dir:
            output_dir = Path(temp_dir) / "frames"
            try:
                extract_frames_at_timestamps(
                    video_path=video_file_path,
                    output_dir=output_dir,
                    timestamps_seconds=frame_timestamps,
                )
                image_paths = sorted(output_dir.glob("*.png"))
            except Exception:
                image_paths = []

            try:
                raw = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=_build_user_prompt(
                        highlight_asset=highlight_asset,
                        subtitle_context=subtitle_context,
                        danmaku_items=danmaku_items,
                        frame_timestamps=frame_timestamps,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=frame_timestamps,
                    max_tokens=self.max_output_tokens,
                )
            except Exception:
                return _fallback_plan(
                    highlight_asset=highlight_asset,
                    display_position=self.display_position,
                )

        return parse_interaction_plan(
            raw,
            highlight_asset=highlight_asset,
            display_position=self.display_position,
        )

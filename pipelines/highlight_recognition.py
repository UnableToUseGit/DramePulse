from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import Any

from pipelines.client import LlmClientProtocol
from pipelines.expression_trigger_detection import (
    ExpressionTriggerPipeline,
    expression_triggers_to_highlight_assets,
    parse_expression_triggers,
)
from pipelines.utils import (
    build_sample_timestamps,
    extract_frames_at_timestamps,
    format_subtitle_timeline,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_system_prompt() -> str:
    return (
        "You are a video highlight recognition model for short dramas. "
        "Find story moments that are suitable for low-friction interaction. "
        "Return only JSON."
    )


def _build_user_prompt(video_id: str, subtitles_timeline: str, timestamps_seconds: list[float]) -> str:
    frame_hint = ", ".join(f"{ts:.3f}s" for ts in timestamps_seconds) if timestamps_seconds else "none"
    return "\n".join(
        [
            f"VIDEO_ID: {video_id}",
            "Task: identify the most interaction-worthy highlights in this short drama.",
            "Output description:",
            "- Only use evidence visible in the sampled frames and subtitles.",
            "- Do not invent plot details, character identities, emotions, or motives.",
            "- Prefer fewer highlights with higher confidence over speculative ones.",
            "- Keep `summary` and `reason` factual and grounded in the provided context.",
            "Output requirement: return JSON with a `highlights` array.",
            "Each highlight object must follow these field rules:",
            "- `start_time`: number in seconds, use the sampled frame or subtitle evidence to choose the start of the highlight.",
            "- `end_time`: number in seconds, must be greater than `start_time`.",
            "- `highlight_type`: short label in English or Chinese, such as identity_reveal, conflict_escalation, sweet_moment, revenge_hitback.",
            "- `emotion`: short label for the strongest user emotion, such as shock, anger, joy, sadness, tension.",
            "- `intensity`: number from 0 to 1 only; 0 means weak, 1 means strongest. Do not use a 5-point scale.",
            "- `summary`: one concise factual sentence describing the highlight.",
            "- `reason`: one concise factual sentence explaining why this scene is worth interaction.",
            "- `confidence`: number from 0 to 1 only; higher means the scene is clearly supported by frames and subtitles.",
            "- If a field cannot be supported directly, lower the confidence or skip that highlight.",
            "- Do not include any extra keys.",
            f"FRAME_TIMESTAMPS: {frame_hint}",
            subtitles_timeline,
        ]
    )


def parse_highlight_assets(
    raw: dict[str, Any] | list[dict[str, Any]] | Any,
    *,
    video_id: str,
    highlight_score: float | None = None,
) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.get("highlights", [])
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    if not isinstance(items, list):
        return []

    now = _now_iso()
    assets: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            intensity = float(item["intensity"])
            confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0 or end_time <= start_time:
            continue
        if not 0.0 <= intensity <= 1.0 or not 0.0 <= confidence <= 1.0:
            continue

        asset = {
            "highlight_id": f"h_{video_id}_{index:03d}",
            "video_id": video_id,
            "start_time": start_time,
            "end_time": end_time,
            "highlight_type": str(item.get("highlight_type", "")).strip(),
            "emotion": str(item.get("emotion", "")).strip(),
            "intensity": intensity,
            "summary": str(item.get("summary", "")).strip(),
            "reason": str(item.get("reason", "")).strip(),
            "confidence": confidence,
            "highlight_score": float(
                item.get("highlight_score", highlight_score if highlight_score is not None else confidence)
            ),
            "status": str(item.get("status", "verified")).strip() or "verified",
            "created_at": str(item.get("created_at", now)),
            "updated_at": str(item.get("updated_at", now)),
        }
        if not asset["highlight_type"] or not asset["emotion"] or not asset["summary"] or not asset["reason"]:
            continue
        assets.append(asset)
    return assets


class HighlightRecognitionPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        sample_interval_sec: float = 1.0,
        max_frames: int | None = None,
        max_output_tokens: int = 1800,
    ) -> None:
        self.llm_client = llm_client
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames
        self.max_output_tokens = max_output_tokens

    def run_expression_triggers(
        self,
        *,
        video_id: str,
        video_file_path: Path,
        subtitle_file_path: Path,
        metadata: dict[str, Any] | None = None,
        danmaku_items: list[Any] | None = None,
        include_finale_trigger: bool = False,
    ) -> list[dict[str, Any]]:
        pipeline = ExpressionTriggerPipeline(
            llm_client=self.llm_client,
            sample_interval_sec=self.sample_interval_sec,
            max_frames=self.max_frames,
            max_output_tokens=max(self.max_output_tokens, 2400),
        )
        return pipeline.run(
            video_id=video_id,
            video_file_path=video_file_path,
            subtitle_file_path=subtitle_file_path,
            metadata=metadata,
            danmaku_items=danmaku_items,
            include_finale_trigger=include_finale_trigger,
        )

    def run(
        self,
        *,
        video_id: str,
        video_file_path: Path,
        subtitle_file_path: Path,
    ) -> list[dict[str, Any]]:
        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitle_duration = max((segment.end for segment in subtitle_segments), default=0.0)
        video_duration = probe_video_duration_seconds(video_file_path)
        duration_sec = max(subtitle_duration, video_duration or 0.0)

        timestamps = build_sample_timestamps(
            duration_sec=duration_sec,
            sample_interval_sec=self.sample_interval_sec,
            max_frames=self.max_frames,
        )
        subtitles_timeline = format_subtitle_timeline(subtitle_segments)

        with tempfile.TemporaryDirectory(prefix=f"highlight_{video_id}_") as temp_dir:
            output_dir = Path(temp_dir) / "frames"
            try:
                extraction = extract_frames_at_timestamps(
                    video_path=video_file_path,
                    output_dir=output_dir,
                    timestamps_seconds=timestamps,
                )
                image_paths = sorted(output_dir.glob("*.png")) if extraction.frame_count > 0 else []
            except Exception:
                image_paths = []

            raw = self.llm_client.generate_json_multimodal(
                system_prompt=_build_system_prompt(),
                user_prompt=_build_user_prompt(video_id, subtitles_timeline, timestamps),
                image_paths=image_paths,
                frame_timestamps_seconds=timestamps,
                max_tokens=self.max_output_tokens,
            )

        if isinstance(raw, dict) and ("expression_triggers" in raw or "triggers" in raw):
            return expression_triggers_to_highlight_assets(parse_expression_triggers(raw, video_id=video_id))
        return parse_highlight_assets(raw, video_id=video_id)

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import Any, Iterable

from pipelines.client import LlmClientProtocol
from pipelines.utils import (
    build_sample_timestamps,
    extract_frames_at_timestamps,
    format_subtitle_timeline,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


SUPPORTED_SOURCE_TYPES = {"plot", "performance", "character_appeal", "finale_judgment"}
SUPPORTED_INTERACTION_MODES = {"single_tap", "hold_burst", "repeat_tap", "stance_poll", "finale_rating"}
PLOT_PRIMARY_EXPRESSION_DEFINITIONS = (
    ("爽到了", "压抑后的反击、打脸、胜利、惩恶扬善带来的解气和爽感。"),
    ("震惊", "身份、真相、关系、能力或局势突然揭晓带来的意外感。"),
    ("气死了", "角色被欺负、被误解、被背叛或反派过分时带来的愤怒。"),
    ("磕到了", "暧昧、甜宠、守护、双向奔赴或亲密关系推进。"),
    ("心疼", "角色受伤、牺牲、隐忍、委屈或处境艰难。"),
    ("紧张", "危机逼近、对峙、追逐、暴露风险或结果悬而未决。"),
    ("站主角", "剧情形成明确立场，用户自然想支持主角或主角阵营。"),
    ("想看后续", "当前信息制造强悬念，用户主要表达继续看下去的欲望。"),
)
SUPPORTED_PLOT_PRIMARY_EXPRESSIONS = {label for label, _description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS}

PERFORMANCE_KEYWORDS = ("笑死", "哈哈", "绷不住", "离谱", "抓马", "尬", "急了", "演技")
CHARACTER_APPEAL_KEYWORDS = ("好帅", "太帅", "太美", "漂亮", "老婆", "老公", "可爱", "眼神", "姐姐")
FINALE_KEYWORDS = ("大结局", "完结", "结局", "好剧", "烂尾", "没看够", "上头", "太短")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _iter_raw_items(raw: Any) -> tuple[list[Any], bool]:
    if isinstance(raw, dict):
        if isinstance(raw.get("expression_triggers"), list):
            return raw["expression_triggers"], False
        if isinstance(raw.get("triggers"), list):
            return raw["triggers"], False
        if isinstance(raw.get("highlights"), list):
            return raw["highlights"], True
    if isinstance(raw, list):
        return raw, False
    return [], False


def _normalize_source_type(value: Any, *, from_legacy_highlight: bool) -> str:
    if from_legacy_highlight:
        return "plot"
    source_type = _clean_text(value)
    return source_type if source_type in SUPPORTED_SOURCE_TYPES else ""


def _normalize_interaction_mode(value: Any, *, source_type: str) -> str:
    interaction_mode = "" if value is None else _clean_text(value)
    if not interaction_mode:
        interaction_mode = "finale_rating" if source_type == "finale_judgment" else "single_tap"
    return interaction_mode if interaction_mode in SUPPORTED_INTERACTION_MODES else ""


def parse_expression_triggers(raw: Any, *, video_id: str) -> list[dict[str, Any]]:
    items, from_legacy_highlight = _iter_raw_items(raw)
    now = _now_iso()
    triggers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            intensity = float(item.get("intensity", item.get("expression_intensity", 0.0)))
            confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0 or end_time <= start_time:
            continue
        if not 0.0 <= intensity <= 1.0 or not 0.0 <= confidence <= 1.0:
            continue

        source_type = _normalize_source_type(item.get("source_type") or item.get("highlight_type"), from_legacy_highlight=from_legacy_highlight)
        if not source_type:
            continue
        interaction_mode = _normalize_interaction_mode(item.get("interaction_mode"), source_type=source_type)
        if not interaction_mode:
            continue

        primary_expression = _clean_text(item.get("primary_expression") or item.get("emotion"))
        summary = _clean_text(item.get("summary"))
        reason = _clean_text(item.get("reason"))
        if not primary_expression or not summary or not reason:
            continue
        if source_type == "plot" and primary_expression not in SUPPORTED_PLOT_PRIMARY_EXPRESSIONS:
            continue

        cue_time = float(item.get("cue_time", start_time + (end_time - start_time) / 2.0))
        cue_time = min(max(start_time, cue_time), end_time)
        trigger = {
            "trigger_id": f"et_{video_id}_{len(triggers) + 1:03d}",
            "video_id": video_id,
            "start_time": _round_time(start_time),
            "end_time": _round_time(end_time),
            "cue_time": _round_time(cue_time),
            "source_type": source_type,
            "primary_expression": primary_expression,
            "interaction_mode": interaction_mode,
            "intensity": intensity,
            "confidence": confidence,
            "summary": summary,
            "reason": reason,
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
            "status": _clean_text(item.get("status", "verified")) or "verified",
            "created_at": str(item.get("created_at", now)),
            "updated_at": str(item.get("updated_at", now)),
        }
        triggers.append(trigger)
    return triggers


def expression_trigger_to_highlight_asset(trigger: dict[str, Any], *, index: int) -> dict[str, Any]:
    video_id = str(trigger["video_id"])
    confidence = float(trigger["confidence"])
    return {
        "highlight_id": f"h_{video_id}_{index:03d}",
        "video_id": video_id,
        "start_time": float(trigger["start_time"]),
        "end_time": float(trigger["end_time"]),
        "highlight_type": str(trigger["source_type"]),
        "emotion": str(trigger["primary_expression"]),
        "intensity": float(trigger["intensity"]),
        "summary": str(trigger["summary"]),
        "reason": str(trigger["reason"]),
        "confidence": confidence,
        "highlight_score": confidence,
        "status": str(trigger.get("status") or "verified"),
        "created_at": str(trigger.get("created_at") or _now_iso()),
        "updated_at": str(trigger.get("updated_at") or _now_iso()),
    }


def expression_triggers_to_highlight_assets(triggers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [expression_trigger_to_highlight_asset(trigger, index=index) for index, trigger in enumerate(triggers, start=1)]


def _danmaku_signal_score(item: dict[str, Any]) -> float:
    count_score = 1.0
    try:
        digg_score = min(float(item.get("digg_count") or 0.0), 20.0) / 10.0
    except (TypeError, ValueError):
        digg_score = 0.0
    try:
        model_score = min(max(float(item.get("score") or 0.0), 0.0), 100.0) / 50.0
    except (TypeError, ValueError):
        model_score = 0.0
    return count_score + digg_score + model_score


def _classify_danmaku_expression(texts: list[str]) -> tuple[str, str] | None:
    joined = "\n".join(texts)
    performance_hits = sum(1 for keyword in PERFORMANCE_KEYWORDS if keyword in joined)
    appeal_hits = sum(1 for keyword in CHARACTER_APPEAL_KEYWORDS if keyword in joined)
    if performance_hits <= 0 and appeal_hits <= 0:
        return None
    if appeal_hits > performance_hits:
        return "character_appeal", "太帅了"
    return "performance", "笑死"


def detect_danmaku_expression_triggers(
    *,
    video_id: str,
    danmaku_items: list[Any],
    duration_sec: float | None,
    window_sec: float = 5.0,
    min_signal_score: float = 3.0,
) -> list[dict[str, Any]]:
    if window_sec <= 0:
        raise ValueError("window_sec must be positive")
    buckets: dict[int, list[dict[str, Any]]] = {}
    for raw_item in danmaku_items:
        if not isinstance(raw_item, dict):
            continue
        text = _clean_text(raw_item.get("text"))
        if not text:
            continue
        try:
            time_sec = float(raw_item["time_sec"])
        except (KeyError, TypeError, ValueError):
            continue
        if time_sec < 0:
            continue
        if duration_sec is not None and duration_sec > 0 and time_sec > duration_sec:
            continue
        bucket_index = int(time_sec // window_sec)
        buckets.setdefault(bucket_index, []).append({**raw_item, "time_sec": time_sec, "text": text})

    now = _now_iso()
    triggers: list[dict[str, Any]] = []
    for bucket_index in sorted(buckets):
        items = buckets[bucket_index]
        texts = [str(item["text"]) for item in items]
        classified = _classify_danmaku_expression(texts)
        if classified is None:
            continue
        signal_score = sum(_danmaku_signal_score(item) for item in items)
        if signal_score < min_signal_score:
            continue
        source_type, primary_expression = classified
        start_time = _round_time(bucket_index * window_sec)
        end_time = _round_time(start_time + window_sec)
        if duration_sec is not None and duration_sec > 0:
            end_time = min(end_time, _round_time(duration_sec))
        top_texts = texts[:5]
        triggers.append(
            {
                "trigger_id": f"et_{video_id}_{len(triggers) + 1:03d}",
                "video_id": video_id,
                "start_time": start_time,
                "end_time": end_time,
                "cue_time": _round_time(start_time + (end_time - start_time) / 2.0),
                "source_type": source_type,
                "primary_expression": primary_expression,
                "interaction_mode": "single_tap",
                "intensity": _clamp01(signal_score / 12.0),
                "confidence": _clamp01(signal_score / 14.0),
                "summary": f"弹幕集中表达「{primary_expression}」。",
                "reason": "该时间窗口出现集中弹幕表达，适合用单按钮承接即时反应。",
                "evidence": {"danmaku_count": len(items), "signal_score": round(signal_score, 3), "top_texts": top_texts},
                "status": "verified",
                "created_at": now,
                "updated_at": now,
            }
        )
    return triggers


def _metadata_indicates_finale(metadata: dict[str, Any] | None) -> bool:
    if not metadata:
        return False
    text = "\n".join(_clean_text(value) for value in metadata.values() if value is not None)
    return any(keyword in text for keyword in ("大结局", "完结", "最终回", "收官"))


def detect_finale_expression_trigger(
    *,
    video_id: str,
    duration_sec: float | None,
    metadata: dict[str, Any] | None = None,
    danmaku_items: list[Any] | None = None,
) -> dict[str, Any] | None:
    if duration_sec is None or duration_sec <= 0:
        return None
    tail_start = duration_sec * 0.85
    tail_items: list[dict[str, Any]] = []
    for raw_item in danmaku_items or []:
        if not isinstance(raw_item, dict):
            continue
        text = _clean_text(raw_item.get("text"))
        if not text:
            continue
        try:
            time_sec = float(raw_item["time_sec"])
        except (KeyError, TypeError, ValueError):
            continue
        if time_sec >= tail_start:
            tail_items.append({**raw_item, "time_sec": time_sec, "text": text})
    tail_text = "\n".join(str(item["text"]) for item in tail_items)
    finale_signal = _metadata_indicates_finale(metadata) or any(keyword in tail_text for keyword in FINALE_KEYWORDS)
    quality_signal = any(keyword in tail_text for keyword in ("好剧", "烂尾", "没看够", "上头", "结局", "太短"))
    if not finale_signal or not (quality_signal or _metadata_indicates_finale(metadata)):
        return None
    now = _now_iso()
    start_time = _round_time(tail_start)
    return {
        "trigger_id": f"et_{video_id}_finale_001",
        "video_id": video_id,
        "start_time": start_time,
        "end_time": _round_time(duration_sec),
        "cue_time": _round_time(start_time + (duration_sec - start_time) / 2.0),
        "source_type": "finale_judgment",
        "primary_expression": "剧终评价",
        "interaction_mode": "finale_rating",
        "intensity": 0.72 if tail_items else 0.55,
        "confidence": 0.78 if quality_signal else 0.62,
        "summary": "剧集尾部适合承接整剧评价。",
        "reason": "剧终场景中用户常表达好剧、烂尾或没看够等整体评价。",
        "evidence": {"danmaku_count": len(tail_items), "top_texts": [str(item["text"]) for item in tail_items[:5]]},
        "status": "verified",
        "created_at": now,
        "updated_at": now,
    }


def _build_system_prompt() -> str:
    return (
        "You identify Expression Triggers in short dramas. "
        "An Expression Trigger is a moment where viewers likely want to tap a low-friction expression, "
        "not merely a narrative turning point. Return JSON only."
    )


def _build_user_prompt(
    *,
    video_id: str,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
    timestamps_seconds: list[float],
) -> str:
    frame_hint = ", ".join(f"{ts:.3f}" for ts in timestamps_seconds) if timestamps_seconds else "none"
    metadata_text = "\n".join(f"- {key}: {value}" for key, value in (metadata or {}).items() if value is not None) or "- none"
    primary_expression_text = "\n".join(f"- {label}: {description}" for label, description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS)
    return "\n".join(
        [
            "## TASK",
            "Identify plot-driven Expression Triggers in a short-drama episode for cold-start player interaction.",
            "An Expression Trigger is a short moment where a viewer would naturally tap a lightweight expression button without pausing or typing.",
            "Use video frames and subtitles together to find moments with clear low-friction expression value, not merely narrative importance.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"FRAME_TIMESTAMPS_SECONDS: {frame_hint}",
            "You will receive one sampled video frame for each timestamp listed above.",
            "You will also receive timestamped subtitle utterances.",
            "[METADATA]",
            metadata_text,
            "[/METADATA]",
            "",
            "## RULES",
            "- Use video frames to understand silent actions, facial expressions, locations, transitions, and visible story situations.",
            "- Use subtitles to understand dialogue, relationship context, and semantic plot progression.",
            "- Only output plot-driven triggers for cold-start detection.",
            "- `source_type` must always be `plot`.",
            "Allowed `primary_expression` values:",
            primary_expression_text,
            "- `primary_expression` must be exactly one of the allowed values above.",
            "- If none of the allowed `primary_expression` values fits clearly, skip the moment.",
            "- Prefer fewer high-confidence triggers over broad plot summaries or generic dramatic moments.",
            "- Skip moments that are only exposition, setup, neutral conversation, or unclear without future context.",
            "- `start_time` and `end_time` should describe the short window where the expression desire appears.",
            "- `cue_time` should be the best moment to show the interaction entry, usually near the emotional release or key reveal.",
            "- Choose times from subtitle/frame evidence. Do not invent events outside the provided timeline.",
            "- `summary` should be one concise factual Chinese sentence grounded in subtitles and/or frames.",
            "- `reason` should explain why this exact moment creates low-friction expression desire, not why it is generally important to the story.",
            "- `intensity` should estimate expression strength from 0.0 to 1.0.",
            "- `confidence` should estimate evidence reliability from 0.0 to 1.0.",
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `expression_triggers`.",
            "Each trigger object must contain exactly these keys: `start_time`, `end_time`, `cue_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `reason`.",
            "Output shape:",
            '{"expression_triggers":[{"start_time":38.0,"end_time":42.0,"cue_time":40.0,"source_type":"plot","primary_expression":"爽到了","intensity":0.86,"confidence":0.82,"summary":"女主当众反击成功。","reason":"压抑后的反击能让用户自然表达解气和爽感。"}]}',
            "Field constraints:",
            "- `start_time`, `end_time`, and `cue_time` are numbers in seconds.",
            "- `start_time` must be >= 0.0.",
            "- `end_time` must be greater than `start_time`.",
            "- `cue_time` must be within [start_time, end_time].",
            "- `source_type` must be `plot`.",
            "- `primary_expression` must be one of the allowed values.",
            "- `intensity` and `confidence` must be numbers from 0.0 to 1.0.",
            "- Do not include any extra keys.",
            "",
            "## SUBTITLE_TIMELINE",
            subtitles_timeline,
        ]
    )


class ExpressionTriggerPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        sample_interval_sec: float = 1.0,
        frames_per_interval: int = 1,
        max_frames: int | None = None,
        max_output_tokens: int = 2400,
    ) -> None:
        self.llm_client = llm_client
        self.sample_interval_sec = sample_interval_sec
        self.frames_per_interval = frames_per_interval
        self.max_frames = max_frames
        self.max_output_tokens = max_output_tokens

    def run(
        self,
        *,
        video_id: str,
        video_file_path: Path,
        subtitle_file_path: Path,
        metadata: dict[str, Any] | None = None,
        danmaku_items: list[Any] | None = None,
        include_finale_trigger: bool = False,
    ) -> list[dict[str, Any]]:
        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitle_duration = max((segment.end for segment in subtitle_segments), default=0.0)
        video_duration = probe_video_duration_seconds(video_file_path)
        danmaku_items = danmaku_items or []
        danmaku_duration = 0.0
        for raw_item in danmaku_items:
            if not isinstance(raw_item, dict):
                continue
            try:
                danmaku_duration = max(danmaku_duration, float(raw_item["time_sec"]))
            except (KeyError, TypeError, ValueError):
                continue
        duration_sec = max(subtitle_duration, video_duration or 0.0, danmaku_duration)
        timestamps = build_sample_timestamps(
            duration_sec=duration_sec,
            sample_interval_sec=self.sample_interval_sec,
            frames_per_interval=self.frames_per_interval,
            max_frames=self.max_frames,
        )
        subtitles_timeline = format_subtitle_timeline(subtitle_segments)

        with tempfile.TemporaryDirectory(prefix=f"expression_{video_id}_") as temp_dir:
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
                user_prompt=_build_user_prompt(
                    video_id=video_id,
                    subtitles_timeline=subtitles_timeline,
                    metadata=metadata,
                    timestamps_seconds=timestamps,
                ),
                image_paths=image_paths,
                frame_timestamps_seconds=timestamps,
                max_tokens=self.max_output_tokens,
            )

        triggers = parse_expression_triggers(raw, video_id=video_id)
        triggers.extend(
            detect_danmaku_expression_triggers(
                video_id=video_id,
                danmaku_items=danmaku_items,
                duration_sec=duration_sec if duration_sec > 0 else None,
            )
        )
        if include_finale_trigger:
            finale_trigger = detect_finale_expression_trigger(
                video_id=video_id,
                duration_sec=duration_sec if duration_sec > 0 else None,
                metadata=metadata,
                danmaku_items=danmaku_items,
            )
            if finale_trigger is not None:
                triggers.append(finale_trigger)
        return sorted(triggers, key=lambda trigger: (float(trigger["start_time"]), str(trigger["trigger_id"])))

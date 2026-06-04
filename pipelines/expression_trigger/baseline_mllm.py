from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import Any, Iterable

from pipelines.client import LlmClientProtocol
from pipelines.utils import (
    SubtitleSegment,
    build_sample_timestamps,
    extract_frames_at_timestamps,
    load_subtitle_segments,
    probe_video_duration_seconds,
)


SUPPORTED_SOURCE_TYPES = {"plot", "performance", "character_appeal", "finale_judgment"}
SUPPORTED_INTERACTION_MODES = {"single_tap", "hold_burst", "repeat_tap", "stance_poll", "finale_rating"}
PLOT_PRIMARY_EXPRESSION_DEFINITIONS = (
    ("爽点", "主角或正义方在被压制、羞辱、质疑或不公平对待之后，当场反击、打脸、赢回主动权或惩罚恶人带来的解气爽感。"),
    ("甜点", "角色之间在暧昧、克制、误会、保护或双向在意的铺垫之后，关系出现明确升温、确认或亲密推进。"),
    ("泪点", "亲情、爱情、牺牲、重逢、告别、无私守护或善意在充分铺垫后兑现，带来感动、悲伤或泪目。"),
    ("笑点", "台词、动作、表演反应、误会、尴尬或前后反差形成明确笑点，观众自然想表达哈哈、笑死或绷不住。"),
)
LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES = {
    "爽到了": "爽点",
    "磕到了": "甜点",
    "看哭了": "泪点",
    "笑死": "笑点",
}
SUPPORTED_PLOT_PRIMARY_EXPRESSIONS = {
    label for label, _description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS
} | set(LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES)

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


def normalize_plot_primary_expression(value: Any) -> str:
    expression = _clean_text(value)
    return LEGACY_PLOT_PRIMARY_EXPRESSION_ALIASES.get(expression, expression)


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

        primary_expression = normalize_plot_primary_expression(item.get("primary_expression") or item.get("emotion"))
        summary = "" if item.get("summary") is None else _clean_text(item.get("summary"))
        reason = "" if item.get("reason") is None else _clean_text(item.get("reason"))
        setup = "" if item.get("setup") is None else _clean_text(item.get("setup"))
        turning_point = "" if item.get("turning_point") is None else _clean_text(item.get("turning_point"))
        expression_release = "" if item.get("expression_release") is None else _clean_text(item.get("expression_release"))
        if not primary_expression:
            continue
        if source_type == "plot" and primary_expression not in SUPPORTED_PLOT_PRIMARY_EXPRESSIONS:
            continue

        payoff_time = float(item.get("payoff_time", item.get("cue_time", start_time + (end_time - start_time) / 2.0)))
        payoff_time = min(max(start_time, payoff_time), end_time)
        trigger = {
            "trigger_id": f"et_{video_id}_{len(triggers) + 1:03d}",
            "video_id": video_id,
            "candidate_id": _clean_text(item.get("candidate_id") or ""),
            "decision": _clean_text(item.get("decision") or ""),
            "role_in_arc": _clean_text(item.get("role_in_arc") or ""),
            "start_time": _round_time(start_time),
            "end_time": _round_time(end_time),
            "story_interval_start": _round_time(start_time),
            "story_interval_end": _round_time(end_time),
            "payoff_time": _round_time(payoff_time),
            "cue_time": _round_time(payoff_time),
            "source_type": source_type,
            "primary_expression": primary_expression,
            "interaction_mode": interaction_mode,
            "intensity": intensity,
            "confidence": confidence,
            "summary": summary,
            "setup": setup,
            "turning_point": turning_point,
            "expression_release": expression_release,
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
        "setup": str(trigger.get("setup") or ""),
        "turning_point": str(trigger.get("turning_point") or ""),
        "expression_release": str(trigger.get("expression_release") or ""),
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
    return "performance", "笑点"


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


def format_expression_subtitle_timeline_seconds(segments: list[SubtitleSegment]) -> str:
    lines = ["[SUBTITLE_TIMELINE]"]
    for segment in segments:
        text = " ".join(segment.text.split())
        lines.append(f"[{segment.start:.3f}-{segment.end:.3f}] {text}")
    lines.append("[/SUBTITLE_TIMELINE]")
    return "\n".join(lines)


def filter_triggers_within_duration(triggers: list[dict[str, Any]], *, duration_sec: float) -> list[dict[str, Any]]:
    if duration_sec <= 0:
        return triggers
    filtered: list[dict[str, Any]] = []
    for trigger in triggers:
        try:
            start_time = float(trigger["start_time"])
            end_time = float(trigger["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 <= start_time <= duration_sec and end_time <= duration_sec:
            filtered.append(trigger)
    return filtered


def _build_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
    timestamps_seconds: list[float],
) -> str:
    frame_hint = ", ".join(f"{ts:.3f}" for ts in timestamps_seconds) if timestamps_seconds else "none"
    metadata_text = "\n".join(f"- {key}: {value}" for key, value in (metadata or {}).items() if value is not None) or "- none"
    expression_definitions = {
        label: description for label, description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS
    }
    return "\n".join(
        [
            "## TASK",
            "Identify plot-driven Expression Triggers in a short-drama episode for cold-start player interaction.",
            "An Expression Trigger is a short moment where a viewer would naturally tap a lightweight expression button without pausing or typing.",
            "Use video frames and subtitles together to find moments with clear low-friction expression value, not merely narrative importance.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            f"FRAME_TIMESTAMPS_SECONDS: {frame_hint}",
            "You will receive one sampled video frame for each timestamp listed above.",
            "You will also receive timestamped subtitle utterances.",
            "All subtitle timestamps and output times are plain seconds, not MM:SS or HH:MM:SS.",
            "[METADATA]",
            metadata_text,
            "[/METADATA]",
            "",
            "## EVIDENCE",
            "- Use video frames to understand silent actions, facial expressions, locations, transitions, and visible story situations.",
            "- Use subtitles to understand dialogue, relationship context, and semantic plot progression.",
            "- Only output plot-driven triggers for cold-start detection.",
            "- `source_type` must always be `plot`.",
            "",
            "## DECISION PROCESS",
            "1. First decide whether the moment is an emotional release point.",
            "2. Verify the release structure: prior setup -> current turning point -> expression release.",
            "3. Match exactly one `primary_expression` from `## PRIMARY_EXPRESSIONS`.",
            "4. If the moment is only setup, exposition, hardship, danger relief, approval, recruitment, opportunity, generic support, or curiosity, skip it.",
            "5. Choose `cue_time` after the viewer understands the release.",
            "",
            "## GATING RULES",
            "- `primary_expression` must be exactly one of the allowed values above.",
            "- If none of the allowed `primary_expression` values fits clearly, skip the moment.",
            "- A valid trigger must be an emotional release point, not merely the moment where a bad, sad, tense, or important event happens.",
            "- A release point requires setup before the current moment and a clear turning point at the current moment.",
            "- Prefer fewer high-confidence triggers over broad plot summaries or generic dramatic moments.",
            "- Skip moments that are only exposition, setup, neutral conversation, or unclear without future context.",
            "- Skip moments that only create anger, pity, worry, support, or curiosity without an immediate release point.",
            "",
            "## PRIMARY_EXPRESSIONS",
            "### 爽点",
            f"Definition: {expression_definitions['爽点']}",
            "Required: the protagonist or justice side actively regains power, wins, exposes, punishes, or face-slaps at this moment.",
            "Reject: simple danger relief, being helped by someone else, being recognized, receiving an opportunity, or a generic positive turn.",
            "",
            "### 甜点",
            f"Definition: {expression_definitions['甜点']}",
            "Required: prior relationship tension, ambiguity, restraint, misunderstanding, protection, or mutual care before clear relationship advancement.",
            "Reject: ordinary help, politeness, teamwork, or protection without relationship advancement.",
            "",
            "### 泪点",
            f"Definition: {expression_definitions['泪点']}",
            "Required: emotional payoff such as sacrifice, reunion, farewell, selfless protection, forgiveness, or family/love breakthrough.",
            "Reject: mere hardship, pity, bullying, debt pressure, or ordinary sadness without emotional payoff.",
            "",
            "### 笑点",
            f"Definition: {expression_definitions['笑点']}",
            "Required: a visible or subtitle-supported comedic beat such as punchline, physical gag, awkward reversal, absurd reaction, misunderstanding, or comic timing.",
            "Reject: ordinary light tone, generic cuteness, actor charm, or comments that are only funny because of external fandom context.",
            "",
            "## TIMING",
            "- `start_time` and `end_time` describe the short emotional release window.",
            "- `cue_time` is the interaction entry moment inside that window.",
            "- Prefer `cue_time` on a reaction shot, pause, emotional aftertaste, or immediately after the turning point.",
            "- Do not place `cue_time` before the viewer understands the key line/action.",
            "- Choose times from subtitle/frame evidence. Do not invent events outside the provided timeline.",
            "- All output times must be between 0.0 and VIDEO_DURATION_SECONDS.",
            "",
            "## FIELD WRITING",
            "- Every trigger should explain the release structure with `setup`, `turning_point`, and `expression_release` when evidence is clear.",
            "- `setup` should state what prior disadvantage, expectation, misdirection, restraint, relationship tension, humiliation, low status, or emotional pressure was built before this moment.",
            "- `turning_point` should state what changes at this exact moment: counterattack, face-slap, win, reveal, relationship advancement, reunion, sacrifice, emotional breakthrough, vow, awakening, or decisive life choice.",
            "- `expression_release` should state what accumulated emotion is released after the key line/action lands and why the viewer would want to tap now.",
            "- `summary` should be one concise factual Chinese sentence grounded in subtitles and/or frames.",
            "- `reason` should summarize why this exact moment is an emotional release point, not why it is generally important to the story.",
            "- If evidence for `summary`, `setup`, `turning_point`, `expression_release`, or `reason` is unclear, output an empty string for that field instead of omitting the key.",
            "- `intensity` should estimate expression strength from 0.0 to 1.0.",
            "- `confidence` should estimate evidence reliability from 0.0 to 1.0.",
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `expression_triggers`.",
            "Each trigger object must contain exactly these keys: `start_time`, `end_time`, `cue_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `setup`, `turning_point`, `expression_release`, `reason`.",
            "Use this exact object template for every trigger, in this exact key order:",
            '{"start_time":0.0,"end_time":0.0,"cue_time":0.0,"source_type":"plot","primary_expression":"爽点","intensity":0.0,"confidence":0.0,"summary":"","setup":"","turning_point":"","expression_release":"","reason":""}',
            "Never output a bare string value after `summary`; the next key must be `setup`.",
            "Never omit a key. If a text field is uncertain, keep the key and set its value to an empty string.",
            "Output shape:",
            '{"expression_triggers":[{"start_time":38.0,"end_time":42.0,"cue_time":40.0,"source_type":"plot","primary_expression":"爽点","intensity":0.86,"confidence":0.82,"summary":"女主当众反击成功。","setup":"女主此前被反派压制和羞辱。","turning_point":"女主抓住证据当众反击反派。","expression_release":"前面的压抑在反击时释放，观众自然想表达解气。","reason":"该点不是单纯冲突，而是压抑后的打脸释放点。"}]}',
            "Field constraints:",
            "- `start_time`, `end_time`, and `cue_time` are numbers in seconds.",
            "- `start_time` must be >= 0.0.",
            "- `end_time` must be greater than `start_time`.",
            "- `end_time` must be <= VIDEO_DURATION_SECONDS.",
            "- `cue_time` must be within [start_time, end_time].",
            "- `source_type` must be `plot`.",
            "- `primary_expression` must be one of the allowed values.",
            "- `summary`, `setup`, `turning_point`, `expression_release`, and `reason` are strings. Use an empty string only if the evidence is unclear.",
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
        max_frames: int | None = None,
        max_output_tokens: int = 2400,
        enable_danmaku_enhancement: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.sample_interval_sec = sample_interval_sec
        self.max_frames = max_frames
        self.max_output_tokens = max_output_tokens
        self.enable_danmaku_enhancement = enable_danmaku_enhancement
        self.last_llm_call: dict[str, Any] = {}

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
            max_frames=self.max_frames,
        )
        subtitles_timeline = format_expression_subtitle_timeline_seconds(subtitle_segments)

        with tempfile.TemporaryDirectory(prefix=f"expression_{video_id}_") as temp_dir:
            output_dir = Path(temp_dir) / "frames"
            try:
                extraction = extract_frames_at_timestamps(
                    video_path=video_file_path,
                    output_dir=output_dir,
                    timestamps_seconds=timestamps,
                    max_height=512,
                )
                image_paths = sorted(output_dir.glob("*.png")) if extraction.frame_count > 0 else []
            except Exception:
                image_paths = []

            try:
                raw = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=_build_user_prompt(
                        video_id=video_id,
                        video_duration_seconds=duration_sec,
                        subtitles_timeline=subtitles_timeline,
                        metadata=metadata,
                        timestamps_seconds=timestamps,
                    ),
                    image_paths=image_paths,
                    frame_timestamps_seconds=timestamps,
                    max_tokens=self.max_output_tokens,
                )
            finally:
                diagnostics = getattr(self.llm_client, "last_call_diagnostics", {})
                self.last_llm_call = dict(diagnostics) if isinstance(diagnostics, dict) else {}

        triggers = filter_triggers_within_duration(parse_expression_triggers(raw, video_id=video_id), duration_sec=duration_sec)
        if self.enable_danmaku_enhancement:
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

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines.client import LlmClientProtocol
from pipelines.expression_trigger_detection import (
    PLOT_PRIMARY_EXPRESSION_DEFINITIONS,
    _build_system_prompt,
    filter_triggers_within_duration,
    format_expression_subtitle_timeline_seconds,
    parse_expression_triggers,
)
from pipelines.utils import load_subtitle_segments


def _build_text_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
) -> str:
    metadata_text = "\n".join(f"- {key}: {value}" for key, value in (metadata or {}).items() if value is not None) or "- none"
    expression_definitions = {label: description for label, description in PLOT_PRIMARY_EXPRESSION_DEFINITIONS}
    return "\n".join(
        [
            "## TASK",
            "Identify plot-driven Expression Triggers in a short-drama episode for cold-start player interaction.",
            "An Expression Trigger is a short moment where a viewer would naturally tap a lightweight expression button without pausing or typing.",
            "Use timestamped subtitles to find moments with clear low-friction expression value, not merely narrative importance.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "You will receive timestamped subtitle utterances only.",
            "All subtitle timestamps and output times are plain seconds, not MM:SS or HH:MM:SS.",
            "[METADATA]",
            metadata_text,
            "[/METADATA]",
            "",
            "## EVIDENCE",
            "- Use subtitles to infer dialogue beats, relationship context, callbacks, contrast, and semantic plot progression.",
            "- Do not assume silent visual actions unless they are directly implied by subtitles.",
            "- Only output plot-driven triggers for cold-start detection.",
            "- `source_type` must always be `plot`.",
            "",
            "## DECISION PROCESS",
            "1. First decide whether the subtitle moment is an emotional release point.",
            "2. Verify the release structure: prior subtitle setup -> current line/action implication -> expression release.",
            "3. Match exactly one `primary_expression` from `## PRIMARY_EXPRESSIONS`.",
            "4. If the moment is only setup, exposition, hardship, danger relief, approval, recruitment, opportunity, generic support, or curiosity, skip it.",
            "5. Choose `cue_time` after the viewer understands the release from the subtitle line.",
            "",
            "## GATING RULES",
            "- `primary_expression` must be exactly one of the allowed values above.",
            "- If none of the allowed `primary_expression` values fits clearly, skip the moment.",
            "- A valid trigger must be an emotional release point, not merely the moment where a bad, sad, tense, or important event happens.",
            "- A release point requires setup before the current subtitle moment and a clear turning point at the current moment.",
            "- Prefer fewer high-confidence triggers over broad plot summaries or generic dramatic moments.",
            "- Skip moments that are only exposition, setup, neutral conversation, or unclear without future context.",
            "- Skip moments that only create anger, pity, worry, support, or curiosity without an immediate release point.",
            "- When subtitles are ambiguous, lower confidence or skip the trigger instead of inventing missing visual evidence.",
            "",
            "## PRIMARY_EXPRESSIONS",
            "### 爽到了",
            f"Definition: {expression_definitions['爽到了']}",
            "Required: the protagonist or justice side actively regains power, wins, exposes, punishes, or face-slaps at this moment.",
            "Reject: simple danger relief, being helped by someone else, being recognized, receiving an opportunity, or a generic positive turn.",
            "",
            "### 磕到了",
            f"Definition: {expression_definitions['磕到了']}",
            "Required: prior relationship tension, ambiguity, restraint, misunderstanding, protection, or mutual care before clear relationship advancement.",
            "Reject: ordinary help, politeness, teamwork, or protection without relationship advancement.",
            "",
            "### 看哭了",
            f"Definition: {expression_definitions['看哭了']}",
            "Required: emotional payoff such as sacrifice, reunion, farewell, selfless protection, forgiveness, or family/love breakthrough.",
            "Reject: mere hardship, pity, bullying, debt pressure, or ordinary sadness without emotional payoff.",
            "",
            "### 笑死",
            f"Definition: {expression_definitions['笑死']}",
            "Required: a subtitle-supported comedic beat such as punchline, awkward reversal, absurd reaction, misunderstanding, or comic timing.",
            "Reject: ordinary light tone, generic cuteness, actor charm, or comments that are only funny because of external fandom context.",
            "",
            "## TIMING",
            "- `start_time` and `end_time` describe the short emotional release window.",
            "- `cue_time` is the interaction entry moment inside that window.",
            "- `cue_time` should be at or just after the subtitle line where the release lands.",
            "- Do not place `cue_time` before the viewer understands the key line.",
            "- Choose times from subtitle evidence. Do not invent events outside the provided timeline.",
            "- All output times must be between 0.0 and VIDEO_DURATION_SECONDS.",
            "",
            "## FIELD WRITING",
            "- Every trigger should explain the release structure with `setup`, `turning_point`, and `expression_release` when evidence is clear.",
            "- `setup` should state what prior disadvantage, expectation, restraint, relationship tension, humiliation, low status, or emotional pressure was built before this moment.",
            "- `turning_point` should state what changes at this exact subtitle moment: counterattack, face-slap, win, relationship advancement, reunion, sacrifice, emotional breakthrough, punchline, or comic reversal.",
            "- `expression_release` should state what accumulated emotion is released after the key line lands and why the viewer would want to tap now.",
            "- `summary` should be one concise factual Chinese sentence grounded in subtitles.",
            "- `reason` should summarize why this exact moment is an emotional release point, not why it is generally important to the story.",
            "- If evidence for `summary`, `setup`, `turning_point`, `expression_release`, or `reason` is unclear, output an empty string for that field instead of omitting the key.",
            "- `intensity` should estimate expression strength from 0.0 to 1.0.",
            "- `confidence` should estimate subtitle evidence reliability from 0.0 to 1.0.",
            "",
            "## OUTPUT",
            "Return JSON only. Do not wrap it in markdown.",
            "The top-level object must contain exactly one key: `expression_triggers`.",
            "Each trigger object must contain exactly these keys: `start_time`, `end_time`, `cue_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `setup`, `turning_point`, `expression_release`, `reason`.",
            "Use this exact object template for every trigger, in this exact key order:",
            '{"start_time":0.0,"end_time":0.0,"cue_time":0.0,"source_type":"plot","primary_expression":"爽到了","intensity":0.0,"confidence":0.0,"summary":"","setup":"","turning_point":"","expression_release":"","reason":""}',
            "Never output a bare string value after `summary`; the next key must be `setup`.",
            "Never omit a key. If a text field is uncertain, keep the key and set its value to an empty string.",
            "Output shape:",
            '{"expression_triggers":[{"start_time":38.0,"end_time":42.0,"cue_time":40.0,"source_type":"plot","primary_expression":"爽到了","intensity":0.86,"confidence":0.82,"summary":"女主当众反击成功。","setup":"女主此前被反派压制和羞辱。","turning_point":"女主抓住证据当众反击反派。","expression_release":"前面的压抑在反击时释放，观众自然想表达解气。","reason":"该点不是单纯冲突，而是压抑后的打脸释放点。"}]}',
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


class TextExpressionTriggerPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        max_output_tokens: int = 2400,
    ) -> None:
        self.llm_client = llm_client
        self.max_output_tokens = max_output_tokens
        self.last_llm_call: dict[str, Any] = {}

    def run(
        self,
        *,
        video_id: str,
        subtitle_file_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        subtitle_segments = load_subtitle_segments(subtitle_file_path)
        subtitle_duration = max((segment.end for segment in subtitle_segments), default=0.0)
        subtitles_timeline = format_expression_subtitle_timeline_seconds(subtitle_segments)
        try:
            raw = self.llm_client.generate_json_multimodal(
                system_prompt=_build_system_prompt(),
                user_prompt=_build_text_user_prompt(
                    video_id=video_id,
                    video_duration_seconds=subtitle_duration,
                    subtitles_timeline=subtitles_timeline,
                    metadata=metadata,
                ),
                image_paths=[],
                frame_timestamps_seconds=[],
                max_tokens=self.max_output_tokens,
            )
        finally:
            diagnostics = getattr(self.llm_client, "last_call_diagnostics", {})
            self.last_llm_call = dict(diagnostics) if isinstance(diagnostics, dict) else {}

        return filter_triggers_within_duration(parse_expression_triggers(raw, video_id=video_id), duration_sec=subtitle_duration)

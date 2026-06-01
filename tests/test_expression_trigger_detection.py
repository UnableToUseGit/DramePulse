from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipelines.expression_trigger_detection import (
    ExpressionTriggerPipeline,
    _build_user_prompt,
    detect_danmaku_expression_triggers,
    detect_finale_expression_trigger,
    expression_trigger_to_highlight_asset,
    parse_expression_triggers,
)


class ParseExpressionTriggersTest(unittest.TestCase):
    def test_parse_expression_triggers_normalizes_valid_llm_payload(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 38.0,
                        "end_time": 42.0,
                        "cue_time": 40.0,
                        "source_type": "plot",
                        "primary_expression": "爽到了",
                        "interaction_mode": "single_tap",
                        "intensity": 0.88,
                        "confidence": 0.82,
                        "summary": "女主当众反击。",
                        "reason": "压抑后的反击适合低摩擦表达爽感。",
                        "setup": "女主先前被当众质疑和压制。",
                        "turning_point": "女主抓住证据完成反击。",
                        "expression_release": "压抑后的打脸让观众想表达爽感。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(len(triggers), 1)
        trigger = triggers[0]
        self.assertEqual(trigger["trigger_id"], "et_demo_ep01_001")
        self.assertEqual(trigger["source_type"], "plot")
        self.assertEqual(trigger["primary_expression"], "爽到了")
        self.assertEqual(trigger["interaction_mode"], "single_tap")
        self.assertEqual(trigger["setup"], "女主先前被当众质疑和压制。")
        self.assertEqual(trigger["turning_point"], "女主抓住证据完成反击。")
        self.assertEqual(trigger["expression_release"], "压抑后的打脸让观众想表达爽感。")
        self.assertEqual(trigger["status"], "verified")

    def test_parse_expression_triggers_defaults_interaction_mode_when_llm_omits_it(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 38.0,
                        "end_time": 42.0,
                        "cue_time": 40.0,
                        "source_type": "plot",
                        "primary_expression": "爽到了",
                        "intensity": 0.88,
                        "confidence": 0.82,
                        "summary": "女主当众反击。",
                        "reason": "压抑后的反击适合低摩擦表达爽感。",
                        "setup": "女主此前一直被压制。",
                        "turning_point": "女主当众完成反击。",
                        "expression_release": "观众在反击释放点表达爽感。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["interaction_mode"], "single_tap")

    def test_parse_expression_triggers_rejects_plot_trigger_without_release_structure(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 38.0,
                        "end_time": 42.0,
                        "cue_time": 40.0,
                        "source_type": "plot",
                        "primary_expression": "爽到了",
                        "intensity": 0.88,
                        "confidence": 0.82,
                        "summary": "女主当众反击。",
                        "reason": "压抑后的反击适合低摩擦表达爽感。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(triggers, [])

    def test_parse_expression_triggers_rejects_unsupported_source_type(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "source_type": "narrative_turning_point",
                        "primary_expression": "反转了",
                        "interaction_mode": "single_tap",
                        "intensity": 0.5,
                        "confidence": 0.5,
                        "summary": "剧情变化。",
                        "reason": "这是旧假设。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(triggers, [])

    def test_parse_expression_triggers_rejects_unsupported_plot_expression(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "source_type": "plot",
                        "primary_expression": "站女主",
                        "intensity": 0.5,
                        "confidence": 0.5,
                        "summary": "女主受到支持。",
                        "reason": "这是自由文本表达。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(triggers, [])

    def test_parse_expression_triggers_accepts_tearful_plot_expression(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 18.0,
                        "end_time": 22.0,
                        "source_type": "plot",
                        "primary_expression": "看哭了",
                        "intensity": 0.7,
                        "confidence": 0.8,
                        "summary": "女主终于和亲人重逢。",
                        "reason": "重逢情节容易让用户感动落泪。",
                        "setup": "亲人长期分离，女主一直压抑思念。",
                        "turning_point": "两人在当前时刻终于重逢。",
                        "expression_release": "重逢释放了前面的思念和委屈。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["primary_expression"], "看哭了")

    def test_parse_expression_triggers_accepts_rising_plot_expression(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 46.0,
                        "end_time": 51.0,
                        "cue_time": 50.0,
                        "source_type": "plot",
                        "primary_expression": "燃起来了",
                        "intensity": 0.82,
                        "confidence": 0.86,
                        "summary": "男主受辱后立誓一定要出人头地。",
                        "reason": "该点是低谷后的立志觉醒，不是当场反击打脸。",
                        "setup": "男主此前贫穷潦倒，还被村民讨债羞辱。",
                        "turning_point": "男主明确喊出自己一定要出人头地。",
                        "expression_release": "受辱后的不甘转化为逆袭决心，观众适合表达燃起来了。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["primary_expression"], "燃起来了")

    def test_parse_expression_triggers_accepts_comedy_plot_expression(self) -> None:
        triggers = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 24.0,
                        "end_time": 28.0,
                        "cue_time": 26.2,
                        "source_type": "plot",
                        "primary_expression": "笑死",
                        "intensity": 0.78,
                        "confidence": 0.84,
                        "summary": "男主踹门失败后摔倒，还尴尬地向老板拜年。",
                        "reason": "动作失误和台词反差形成明确笑点。",
                        "setup": "男主带人气势汹汹上门讨债。",
                        "turning_point": "男主踹门后失去气势，摔倒在地并尴尬拜年。",
                        "expression_release": "讨债气势和狼狈反应形成反差，观众适合表达笑死。",
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["primary_expression"], "笑死")

    def test_expression_trigger_maps_to_highlight_asset_contract_fields(self) -> None:
        trigger = parse_expression_triggers(
            {
                "expression_triggers": [
                    {
                        "start_time": 10.0,
                        "end_time": 12.0,
                        "source_type": "plot",
                        "primary_expression": "震惊",
                        "interaction_mode": "single_tap",
                        "intensity": 0.7,
                        "confidence": 0.8,
                        "summary": "身份突然揭晓。",
                        "reason": "用户适合表达震惊。",
                        "setup": "角色身份此前一直被隐藏。",
                        "turning_point": "当前时刻揭晓真实身份。",
                        "expression_release": "认知反差让观众立刻想表达震惊。",
                    }
                ]
            },
            video_id="demo_ep01",
        )[0]

        asset = expression_trigger_to_highlight_asset(trigger, index=1)

        self.assertEqual(asset["highlight_id"], "h_demo_ep01_001")
        self.assertEqual(asset["video_id"], "demo_ep01")
        self.assertEqual(asset["highlight_type"], "plot")
        self.assertEqual(asset["emotion"], "震惊")
        self.assertEqual(asset["highlight_score"], 0.8)
        self.assertNotIn("interaction_mode", asset)


class DanmakuEnhancementTest(unittest.TestCase):
    def test_detect_danmaku_expression_triggers_detects_performance_laugh_peak(self) -> None:
        triggers = detect_danmaku_expression_triggers(
            video_id="demo_ep01",
            danmaku_items=[
                {"time_sec": 20.1, "text": "笑死我了", "digg_count": 4, "score": 1.0},
                {"time_sec": 21.2, "text": "哈哈哈哈绷不住", "digg_count": 2, "score": 1.0},
                {"time_sec": 22.0, "text": "太离谱了", "digg_count": 1, "score": 1.0},
            ],
            duration_sec=90.0,
            min_signal_score=3.0,
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["source_type"], "performance")
        self.assertEqual(triggers[0]["primary_expression"], "笑死")
        self.assertEqual(triggers[0]["interaction_mode"], "single_tap")

    def test_detect_danmaku_expression_triggers_detects_character_appeal_peak(self) -> None:
        triggers = detect_danmaku_expression_triggers(
            video_id="demo_ep01",
            danmaku_items=[
                {"time_sec": 45.0, "text": "男主好帅", "digg_count": 3, "score": 1.0},
                {"time_sec": 46.0, "text": "这个眼神绝了", "digg_count": 2, "score": 1.0},
                {"time_sec": 47.0, "text": "老公", "digg_count": 1, "score": 1.0},
            ],
            duration_sec=90.0,
            min_signal_score=3.0,
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["source_type"], "character_appeal")
        self.assertEqual(triggers[0]["primary_expression"], "太帅了")

    def test_detect_finale_expression_trigger_only_uses_tail_window(self) -> None:
        trigger = detect_finale_expression_trigger(
            video_id="demo_ep01",
            duration_sec=100.0,
            metadata={"title": "第 80 集 大结局"},
            danmaku_items=[
                {"time_sec": 12.0, "text": "这剧太上头了"},
                {"time_sec": 94.0, "text": "好剧没看够"},
                {"time_sec": 96.0, "text": "大结局有点烂尾"},
            ],
        )

        self.assertIsNotNone(trigger)
        assert trigger is not None
        self.assertEqual(trigger["source_type"], "finale_judgment")
        self.assertEqual(trigger["interaction_mode"], "finale_rating")
        self.assertEqual(trigger["primary_expression"], "剧终评价")


class ExpressionTriggerPromptTest(unittest.TestCase):
    def test_build_user_prompt_uses_decision_process_and_separate_rule_sections(self) -> None:
        prompt = _build_user_prompt(
            video_id="demo_ep01",
            subtitles_timeline="[1.000-2.000] 你终于输了",
            metadata={"title": "第 1 集", "series_name": "测试短剧"},
            timestamps_seconds=[0.0, 1.0, 2.0],
        )

        self.assertIn("## TASK", prompt)
        self.assertIn("## INPUT", prompt)
        self.assertIn("## DECISION PROCESS", prompt)
        self.assertIn("## GATING RULES", prompt)
        self.assertIn("## PRIMARY_EXPRESSIONS", prompt)
        self.assertIn("## TIMING", prompt)
        self.assertIn("## FIELD WRITING", prompt)
        self.assertIn("## OUTPUT", prompt)
        self.assertIn("VIDEO_ID: demo_ep01", prompt)
        self.assertIn("FRAME_TIMESTAMPS_SECONDS: 0.000, 1.000, 2.000", prompt)
        self.assertIn("You will receive one sampled video frame for each timestamp listed above.", prompt)
        self.assertIn("Use video frames to understand silent actions, facial expressions, locations, transitions, and visible story situations.", prompt)
        self.assertIn("Use subtitles to understand dialogue, relationship context, and semantic plot progression.", prompt)
        self.assertIn("1. First decide whether the moment is an emotional release point.", prompt)
        self.assertIn("2. Verify the release structure: prior setup -> current turning point -> expression release.", prompt)
        self.assertIn("3. Match exactly one `primary_expression` from `## PRIMARY_EXPRESSIONS`.", prompt)
        self.assertIn("5. Choose `cue_time` after the viewer understands the release.", prompt)
        self.assertIn("### 爽到了", prompt)
        self.assertIn("Definition: 主角或正义方在被压制、羞辱、质疑或不公平对待之后，当场反击、打脸、赢回主动权或惩罚恶人带来的解气爽感。", prompt)
        self.assertIn("Reject: simple danger relief, being helped by someone else, being recognized, receiving an opportunity, or a generic positive turn.", prompt)
        self.assertIn("### 震惊", prompt)
        self.assertIn("### 磕到了", prompt)
        self.assertIn("### 看哭了", prompt)
        self.assertIn("Reject: mere hardship, pity, bullying, debt pressure, or ordinary sadness without emotional payoff.", prompt)
        self.assertIn("### 燃起来了", prompt)
        self.assertIn("Required: a clear vow, awakening, irreversible choice, or decision to change fate after low status, humiliation, poverty, failure, or being underestimated.", prompt)
        self.assertIn("Reject: generic approval, help, recruitment, or opportunity unless the protagonist makes an explicit inner turn or decisive choice.", prompt)
        self.assertIn("### 笑死", prompt)
        self.assertIn("Definition: 台词、动作、表演反应、误会、尴尬或前后反差形成明确笑点，观众自然想表达哈哈、笑死或绷不住。", prompt)
        self.assertIn("Required: a visible or subtitle-supported comedic beat such as punchline, physical gag, awkward reversal, absurd reaction, misunderstanding, or comic timing.", prompt)
        self.assertIn("Reject: ordinary light tone, generic cuteness, actor charm, or comments that are only funny because of external fandom context.", prompt)
        self.assertNotIn("气死了", prompt)
        self.assertNotIn("心疼", prompt)
        self.assertNotIn("紧张", prompt)
        self.assertNotIn("站主角", prompt)
        self.assertNotIn("想看后续", prompt)
        self.assertIn("If none of the allowed `primary_expression` values fits clearly, skip the moment.", prompt)
        self.assertIn("`start_time` and `end_time` describe the short emotional release window.", prompt)
        self.assertIn("`cue_time` is the interaction entry moment inside that window.", prompt)
        self.assertIn("Prefer `cue_time` on a reaction shot, pause, emotional aftertaste, or immediately after the turning point.", prompt)
        self.assertIn("The top-level object must contain exactly one key: `expression_triggers`.", prompt)
        self.assertIn("Each trigger object must contain exactly these keys: `start_time`, `end_time`, `cue_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `setup`, `turning_point`, `expression_release`, `reason`.", prompt)
        self.assertIn('{"expression_triggers":[{"start_time":38.0,"end_time":42.0,"cue_time":40.0,"source_type":"plot","primary_expression":"爽到了","intensity":0.86,"confidence":0.82,"summary":"女主当众反击成功。","setup":"女主此前被反派压制和羞辱。","turning_point":"女主抓住证据当众反击反派。","expression_release":"前面的压抑在反击时释放，观众自然想表达解气。","reason":"该点不是单纯冲突，而是压抑后的打脸释放点。"}]}', prompt)
        self.assertNotIn("interaction_mode", prompt)
        self.assertIn("[METADATA]", prompt)
        self.assertIn("- title: 第 1 集", prompt)
        self.assertIn("[1.000-2.000] 你终于输了", prompt)


class ExpressionTriggerPipelineTest(unittest.TestCase):
    def test_pipeline_extracts_frames_with_cost_bounded_height(self) -> None:
        class FakeClient:
            def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, image_paths: list[Path], frame_timestamps_seconds: list[float] | None = None, max_tokens: int = 2400):
                return {"expression_triggers": []}

        class FakeExtraction:
            frame_count = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text("1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n", encoding="utf-8")

            with patch("pipelines.expression_trigger_detection.extract_frames_at_timestamps", return_value=FakeExtraction()) as extract:
                pipeline = ExpressionTriggerPipeline(llm_client=FakeClient(), sample_interval_sec=1.0, max_frames=1)
                pipeline.run(
                    video_id="demo_ep01",
                    video_file_path=video_path,
                    subtitle_file_path=subtitle_path,
                )

        self.assertEqual(extract.call_args.kwargs["max_height"], 512)

    def test_pipeline_combines_cold_start_and_danmaku_triggers(self) -> None:
        class FakeClient:
            def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, image_paths: list[Path], frame_timestamps_seconds: list[float] | None = None, max_tokens: int = 2400):
                self.user_prompt = user_prompt
                return {
                    "expression_triggers": [
                        {
                            "start_time": 5.0,
                            "end_time": 8.0,
                            "source_type": "plot",
                            "primary_expression": "爽到了",
                            "interaction_mode": "single_tap",
                            "intensity": 0.9,
                            "confidence": 0.85,
                            "summary": "女主反击。",
                            "reason": "用户适合表达爽感。",
                            "setup": "女主此前被压制。",
                            "turning_point": "女主当前反击。",
                            "expression_release": "压抑释放形成爽感。",
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text("1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n", encoding="utf-8")

            pipeline = ExpressionTriggerPipeline(llm_client=FakeClient(), sample_interval_sec=1.0, max_frames=1)
            triggers = pipeline.run(
                video_id="demo_ep01",
                video_file_path=video_path,
                subtitle_file_path=subtitle_path,
                metadata={"title": "Demo"},
                danmaku_items=[
                    {"time_sec": 20.0, "text": "笑死我了"},
                    {"time_sec": 21.0, "text": "哈哈哈哈"},
                    {"time_sec": 22.0, "text": "绷不住"},
                ],
            )

        self.assertEqual(triggers[0]["source_type"], "plot")
        self.assertTrue(any(trigger["source_type"] == "performance" for trigger in triggers))

    def test_pipeline_does_not_run_finale_detection_unless_enabled(self) -> None:
        class FakeClient:
            def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, image_paths: list[Path], frame_timestamps_seconds: list[float] | None = None, max_tokens: int = 2400):
                return {"expression_triggers": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text("1\n00:01:40,000 --> 00:01:45,000\n全剧终\n", encoding="utf-8")

            pipeline = ExpressionTriggerPipeline(llm_client=FakeClient(), sample_interval_sec=10.0, max_frames=1)
            disabled = pipeline.run(
                video_id="demo_ep_final",
                video_file_path=video_path,
                subtitle_file_path=subtitle_path,
                metadata={"title": "第 80 集 大结局"},
                danmaku_items=[
                    {"time_sec": 101.0, "text": "好剧没看够"},
                    {"time_sec": 103.0, "text": "大结局有点烂尾"},
                ],
            )
            enabled = pipeline.run(
                video_id="demo_ep_final",
                video_file_path=video_path,
                subtitle_file_path=subtitle_path,
                metadata={"title": "第 80 集 大结局"},
                danmaku_items=[
                    {"time_sec": 101.0, "text": "好剧没看够"},
                    {"time_sec": 103.0, "text": "大结局有点烂尾"},
                ],
                include_finale_trigger=True,
            )

        self.assertFalse(any(trigger["source_type"] == "finale_judgment" for trigger in disabled))
        self.assertTrue(any(trigger["source_type"] == "finale_judgment" for trigger in enabled))


if __name__ == "__main__":
    unittest.main()

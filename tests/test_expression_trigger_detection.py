from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

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
                    }
                ]
            },
            video_id="demo_ep01",
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["interaction_mode"], "single_tap")

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
    def test_build_user_prompt_uses_structured_sections_and_output_contract(self) -> None:
        prompt = _build_user_prompt(
            video_id="demo_ep01",
            subtitles_timeline="[1.000-2.000] 你终于输了",
            metadata={"title": "第 1 集", "series_name": "测试短剧"},
            timestamps_seconds=[0.0, 1.0, 2.0],
        )

        self.assertIn("## TASK", prompt)
        self.assertIn("## INPUT", prompt)
        self.assertIn("## RULES", prompt)
        self.assertIn("## OUTPUT", prompt)
        self.assertIn("VIDEO_ID: demo_ep01", prompt)
        self.assertIn("FRAME_TIMESTAMPS_SECONDS: 0.000, 1.000, 2.000", prompt)
        self.assertIn("You will receive one sampled video frame for each timestamp listed above.", prompt)
        self.assertIn("Use video frames to understand silent actions, facial expressions, locations, transitions, and visible story situations.", prompt)
        self.assertIn("Use subtitles to understand dialogue, relationship context, and semantic plot progression.", prompt)
        self.assertIn("Allowed `primary_expression` values:", prompt)
        self.assertIn("- 爽到了: 压抑后的反击、打脸、胜利、惩恶扬善带来的解气和爽感。", prompt)
        self.assertIn("- 震惊: 身份、真相、关系、能力或局势突然揭晓带来的意外感。", prompt)
        self.assertIn("- 气死了: 角色被欺负、被误解、被背叛或反派过分时带来的愤怒。", prompt)
        self.assertIn("- 磕到了: 暧昧、甜宠、守护、双向奔赴或亲密关系推进。", prompt)
        self.assertIn("- 心疼: 角色受伤、牺牲、隐忍、委屈或处境艰难。", prompt)
        self.assertIn("- 紧张: 危机逼近、对峙、追逐、暴露风险或结果悬而未决。", prompt)
        self.assertIn("- 站主角: 剧情形成明确立场，用户自然想支持主角或主角阵营。", prompt)
        self.assertIn("- 想看后续: 当前信息制造强悬念，用户主要表达继续看下去的欲望。", prompt)
        self.assertIn("If none of the allowed `primary_expression` values fits clearly, skip the moment.", prompt)
        self.assertIn("The top-level object must contain exactly one key: `expression_triggers`.", prompt)
        self.assertIn("Each trigger object must contain exactly these keys: `start_time`, `end_time`, `cue_time`, `source_type`, `primary_expression`, `intensity`, `confidence`, `summary`, `reason`.", prompt)
        self.assertIn('{"expression_triggers":[{"start_time":38.0,"end_time":42.0,"cue_time":40.0,"source_type":"plot","primary_expression":"爽到了","intensity":0.86,"confidence":0.82,"summary":"女主当众反击成功。","reason":"压抑后的反击能让用户自然表达解气和爽感。"}]}', prompt)
        self.assertNotIn("interaction_mode", prompt)
        self.assertIn("[METADATA]", prompt)
        self.assertIn("- title: 第 1 集", prompt)
        self.assertIn("[1.000-2.000] 你终于输了", prompt)


class ExpressionTriggerPipelineTest(unittest.TestCase):
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

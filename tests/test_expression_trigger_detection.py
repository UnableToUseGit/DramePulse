from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipelines.expression_trigger_detection import (
    ExpressionTriggerPipeline,
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


if __name__ == "__main__":
    unittest.main()

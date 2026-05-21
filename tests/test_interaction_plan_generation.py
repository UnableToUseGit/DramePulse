from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from pipelines.interaction_plan_generation import (
    InteractionPlanGenerationPipeline,
    parse_interaction_plan,
)


HIGHLIGHT_ASSET = {
    "highlight_id": "h_v_001_001",
    "video_id": "v_001",
    "start_time": 38.0,
    "end_time": 46.0,
    "highlight_type": "身份揭露",
    "emotion": "震惊",
    "intensity": 0.92,
    "summary": "男主真实身份曝光，反派震惊。",
    "reason": "前文一直铺垫男主被轻视，此处身份反转带来强爽点。",
    "confidence": 0.88,
}


class ParseInteractionPlanTest(unittest.TestCase):
    def test_parse_interaction_plan_fills_system_fields(self) -> None:
        raw = {
            "question": "这波反转你怎么看？",
            "options": [
                {"text": "卧槽反转了", "danmaku_text": "卧槽反转了！", "base_score": 0.8},
                {"text": "爽到了", "danmaku_text": "这波爽到了！", "base_score": 0.7},
            ],
            "feedback": {
                "resonance_text_template": "你和 {ratio}% 的观众一样选择了「{option}」",
            },
        }

        plan = parse_interaction_plan(raw, highlight_asset=HIGHLIGHT_ASSET)

        self.assertEqual(plan["interaction_id"], "i_h_v_001_001")
        self.assertEqual(plan["highlight_id"], "h_v_001_001")
        self.assertEqual(plan["video_id"], "v_001")
        self.assertEqual(plan["trigger_time"], 38.0)
        self.assertEqual(plan["expire_time"], 46.0)
        self.assertEqual(plan["interaction_type"], "danmaku_poll")
        self.assertEqual(plan["display_position"], "subtitle_safe_area")
        self.assertEqual(plan["status"], "active")
        self.assertEqual(plan["options"][0]["option_id"], "o_h_v_001_001_001")
        self.assertEqual(plan["options"][0]["rank"], 1)
        self.assertEqual(plan["feedback"]["type"], "poll_result")
        self.assertTrue(plan["feedback"]["show_ratio"])
        self.assertTrue(plan["feedback"]["show_resonance_text"])

    def test_parse_interaction_plan_uses_fallback_for_invalid_options(self) -> None:
        plan = parse_interaction_plan(
            {"question": "bad", "options": [{"text": "只有一个选项"}]},
            highlight_asset=HIGHLIGHT_ASSET,
        )

        self.assertEqual(plan["question"], "这波反转你怎么看？")
        self.assertEqual([option["text"] for option in plan["options"]], ["卧槽反转了", "爽到了"])


class InteractionPlanGenerationPipelineTest(unittest.TestCase):
    def test_pipeline_builds_prompt_with_highlight_subtitles_and_danmaku(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def generate_json_multimodal(
                self,
                *,
                system_prompt: str,
                user_prompt: str,
                image_paths: list[Path],
                max_tokens: int = 1200,
            ) -> dict[str, object]:
                self.calls.append(
                    {
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "image_paths": image_paths,
                        "max_tokens": max_tokens,
                    }
                )
                return {
                    "question": "这波身份反转你怎么看？",
                    "options": [
                        {"text": "反转了", "danmaku_text": "这也太反转了！"},
                        {"text": "爽到了", "danmaku_text": "爽到了！"},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text(
                "\n".join(
                    [
                        "1",
                        "00:00:20,000 --> 00:00:22,000",
                        "无关前情",
                        "",
                        "2",
                        "00:00:37,000 --> 00:00:41,200",
                        "你根本不知道他是谁。",
                        "",
                        "3",
                        "00:00:41,300 --> 00:00:45,000",
                        "他就是顾氏集团真正的继承人。",
                        "",
                        "4",
                        "00:01:10,000 --> 00:01:12,000",
                        "无关后文",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            client = FakeClient()
            pipeline = InteractionPlanGenerationPipeline(
                llm_client=client,
            )

            plan = pipeline.run(
                highlight_asset=HIGHLIGHT_ASSET,
                video_file_path=video_path,
                subtitle_file_path=subtitle_path,
                danmaku_items=[
                    {"time_sec": 35.8, "text": "前方高能", "digg_count": 2, "score": 3.2},
                    {"time_sec": 39.5, "text": "这个反转绝了", "digg_count": 88, "score": 99.0},
                    {"time_sec": 47.2, "text": "爽文名场面", "digg_count": 12, "score": 17.5},
                ],
            )

        self.assertEqual(plan["question"], "这波身份反转你怎么看？")
        self.assertEqual(plan["interaction_type"], "danmaku_poll")
        self.assertEqual(len(client.calls), 1)
        user_prompt = str(client.calls[0]["user_prompt"])
        self.assertIn("男主真实身份曝光", user_prompt)
        self.assertIn("你根本不知道他是谁。", user_prompt)
        self.assertIn("他就是顾氏集团真正的继承人。", user_prompt)
        self.assertIn("[39.500s] 这个反转绝了", user_prompt)
        self.assertIn("digg=88", user_prompt)
        self.assertIn("score=99.0", user_prompt)
        self.assertIn('"question"', user_prompt)
        self.assertIn('"options"', user_prompt)
        self.assertIn('"danmaku_text"', user_prompt)
        self.assertNotIn("无关前情", user_prompt)
        self.assertNotIn("无关后文", user_prompt)

    def test_pipeline_falls_back_when_llm_raises(self) -> None:
        class FailingClient:
            def generate_json_multimodal(
                self,
                *,
                system_prompt: str,
                user_prompt: str,
                image_paths: list[Path],
                max_tokens: int = 1200,
            ) -> dict[str, object]:
                raise RuntimeError("llm failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text("", encoding="utf-8")

            pipeline = InteractionPlanGenerationPipeline(
                llm_client=FailingClient(),
            )
            plan = pipeline.run(
                highlight_asset={**HIGHLIGHT_ASSET, "highlight_type": "甜蜜撒糖"},
                video_file_path=video_path,
                subtitle_file_path=subtitle_path,
                danmaku_items=[],
            )

        self.assertEqual(plan["question"], "这段什么感觉？")
        self.assertEqual([option["text"] for option in plan["options"]], ["磕到了", "有点甜"])


if __name__ == "__main__":
    unittest.main()

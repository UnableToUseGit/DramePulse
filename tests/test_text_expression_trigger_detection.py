from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipelines.text_expression_trigger_detection import TextExpressionTriggerPipeline, _build_text_user_prompt


class TextExpressionTriggerPromptTest(unittest.TestCase):
    def test_build_text_user_prompt_matches_multimodal_quality_without_frame_requirements(self) -> None:
        prompt = _build_text_user_prompt(
            video_id="demo_ep01",
            video_duration_seconds=123.456,
            subtitles_timeline="[1.000-2.000] 你终于输了",
            metadata={"title": "第 1 集", "series_name": "测试短剧"},
        )

        self.assertIn("## TASK", prompt)
        self.assertIn("## INPUT", prompt)
        self.assertIn("## EVIDENCE", prompt)
        self.assertIn("## DECISION PROCESS", prompt)
        self.assertIn("## GATING RULES", prompt)
        self.assertIn("## PRIMARY_EXPRESSIONS", prompt)
        self.assertIn("## TIMING", prompt)
        self.assertIn("## FIELD WRITING", prompt)
        self.assertIn("## OUTPUT", prompt)
        self.assertIn("VIDEO_ID: demo_ep01", prompt)
        self.assertIn("VIDEO_DURATION_SECONDS: 123.456", prompt)
        self.assertIn("You will receive timestamped subtitle utterances only.", prompt)
        self.assertIn("Use subtitles to infer dialogue beats, relationship context, callbacks, contrast, and semantic plot progression.", prompt)
        self.assertIn("Do not assume silent visual actions unless they are directly implied by subtitles.", prompt)
        self.assertIn("1. First decide whether the subtitle moment is an emotional release point.", prompt)
        self.assertIn("2. Verify the release structure: prior subtitle setup -> current line/action implication -> expression release.", prompt)
        self.assertIn("5. Choose `cue_time` after the viewer understands the release from the subtitle line.", prompt)
        self.assertIn("### 爽点", prompt)
        self.assertIn("### 甜点", prompt)
        self.assertIn("### 泪点", prompt)
        self.assertIn("### 笑点", prompt)
        self.assertNotIn("### 震惊", prompt)
        self.assertNotIn("### 燃起来了", prompt)
        self.assertNotIn("FRAME_TIMESTAMPS_SECONDS", prompt)
        self.assertNotIn("video frame", prompt.lower())
        self.assertIn("`cue_time` should be at or just after the subtitle line where the release lands.", prompt)
        self.assertIn("Every trigger should explain the release structure with `setup`, `turning_point`, and `expression_release`", prompt)
        self.assertIn("The top-level object must contain exactly one key: `expression_triggers`.", prompt)
        self.assertIn("Never output a bare string value after `summary`; the next key must be `setup`.", prompt)
        self.assertIn("[METADATA]", prompt)
        self.assertIn("- title: 第 1 集", prompt)
        self.assertIn("[1.000-2.000] 你终于输了", prompt)


class TextExpressionTriggerPipelineTest(unittest.TestCase):
    def test_pipeline_uses_subtitles_only_and_preserves_llm_diagnostics(self) -> None:
        class FakeClient:
            last_call_diagnostics = {
                "status": "success",
                "elapsed_sec": 0.2,
                "usage": {"total_tokens": 42},
            }

            def generate_json_multimodal(
                self,
                *,
                system_prompt: str,
                user_prompt: str,
                image_paths: list[Path],
                frame_timestamps_seconds: list[float] | None = None,
                max_tokens: int = 2400,
            ) -> dict[str, object]:
                self.system_prompt = system_prompt
                self.user_prompt = user_prompt
                self.image_paths = image_paths
                self.frame_timestamps_seconds = frame_timestamps_seconds
                self.max_tokens = max_tokens
                return {
                    "expression_triggers": [
                        {
                            "start_time": 5.0,
                            "end_time": 8.0,
                            "source_type": "plot",
                            "primary_expression": "爽点",
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
            subtitle_path = Path(tmpdir) / "subtitle.srt"
            subtitle_path.write_text("1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n", encoding="utf-8")

            client = FakeClient()
            pipeline = TextExpressionTriggerPipeline(llm_client=client, max_output_tokens=1234)
            triggers = pipeline.run(
                video_id="demo_ep01",
                subtitle_file_path=subtitle_path,
                metadata={"title": "Demo"},
            )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["primary_expression"], "爽点")
        self.assertEqual(client.image_paths, [])
        self.assertEqual(client.frame_timestamps_seconds, [])
        self.assertEqual(client.max_tokens, 1234)
        self.assertIn("## SUBTITLE_TIMELINE", client.user_prompt)
        self.assertIn("VIDEO_DURATION_SECONDS: 8.000", client.user_prompt)
        self.assertIn("[5.000-8.000] 你终于输了", client.user_prompt)
        self.assertNotIn("[00:05.000 - 00:08.000] 你终于输了", client.user_prompt)
        self.assertEqual(pipeline.last_llm_call["usage"]["total_tokens"], 42)

    def test_pipeline_drops_triggers_outside_subtitle_duration(self) -> None:
        class FakeClient:
            last_call_diagnostics: dict[str, object] = {}

            def generate_json_multimodal(self, **kwargs: object) -> dict[str, object]:
                return {
                    "expression_triggers": [
                        {
                            "start_time": 435.28,
                            "end_time": 455.25,
                            "cue_time": 443.0,
                            "source_type": "plot",
                            "primary_expression": "笑点",
                            "intensity": 0.8,
                            "confidence": 0.8,
                            "summary": "模型把 04:35 误写成 435 秒。",
                            "reason": "越界结果应被过滤。",
                        },
                        {
                            "start_time": 5.0,
                            "end_time": 8.0,
                            "cue_time": 7.0,
                            "source_type": "plot",
                            "primary_expression": "爽点",
                            "intensity": 0.8,
                            "confidence": 0.8,
                            "summary": "女主反击。",
                            "reason": "有效结果应保留。",
                        },
                    ]
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            subtitle_path = Path(tmpdir) / "subtitle.srt"
            subtitle_path.write_text("1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n", encoding="utf-8")

            pipeline = TextExpressionTriggerPipeline(llm_client=FakeClient())
            triggers = pipeline.run(video_id="demo_ep01", subtitle_file_path=subtitle_path)

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["start_time"], 5.0)


if __name__ == "__main__":
    unittest.main()

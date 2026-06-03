from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipelines.workflow_expression_trigger_detection import (
    WorkflowExpressionTriggerPipeline,
    _build_candidate_generation_prompt,
    _build_candidate_filter_prompt,
    build_filter_frame_timestamps,
    consolidate_expression_triggers,
    parse_expression_trigger_candidates,
)


class WorkflowExpressionTriggerPromptTest(unittest.TestCase):
    def test_candidate_generation_prompt_is_high_recall_and_multimodal(self) -> None:
        prompt = _build_candidate_generation_prompt(
            video_id="demo_ep01",
            video_duration_seconds=120.0,
            subtitles_timeline="[5.000-8.000] 你终于输了",
            metadata={"title": "第 1 集"},
            frame_timestamps_seconds=[0.0, 10.0, 20.0],
        )

        self.assertIn("## TASK", prompt)
        self.assertIn("Find candidate story intervals in a short-drama episode where viewers may naturally want to react immediately.", prompt)
        self.assertIn("VIDEO_DURATION_SECONDS: 120.000", prompt)
        self.assertIn("FRAME_TIMESTAMPS_SECONDS: 0.000, 10.000, 20.000", prompt)
        self.assertNotIn("Expression Triggers", prompt)
        self.assertNotIn("filtering stage", prompt)
        self.assertNotIn("second model", prompt)
        self.assertNotIn("请从短剧正片", prompt)
        self.assertNotIn("本阶段", prompt)
        self.assertIn("### 爽到了", prompt)
        self.assertIn("### 磕到了", prompt)
        self.assertIn("### 看哭了", prompt)
        self.assertIn("### 笑死", prompt)
        self.assertIn('"expression_candidates"', prompt)
        self.assertIn('"setup"', prompt)
        self.assertIn('"turning_point"', prompt)
        self.assertIn('"expression_release"', prompt)
        self.assertIn("[5.000-8.000] 你终于输了", prompt)

    def test_candidate_filter_prompt_only_evaluates_given_candidates(self) -> None:
        prompt = _build_candidate_filter_prompt(
            video_id="demo_ep01",
            video_duration_seconds=120.0,
            subtitles_timeline="[5.000-8.000] 你终于输了",
            metadata={"title": "第 1 集"},
            candidates=[
                {
                    "candidate_id": "cand_demo_ep01_001",
                    "start_time": 5.0,
                    "end_time": 12.0,
                    "primary_expression": "爽到了",
                    "summary": "女主反击。",
                    "candidate_reason": "可能是压抑后的反击。",
                }
            ],
        )

        self.assertIn("Review the provided candidate story intervals and keep only the moments where viewers would actually want to react immediately.", prompt)
        self.assertIn("Do not create new moments outside the provided candidates.", prompt)
        self.assertIn("viewer-reaction moment", prompt)
        self.assertIn("candidate_decisions", prompt)
        self.assertIn("decision_reason", prompt)
        self.assertNotIn("Expression Trigger", prompt)
        self.assertNotIn("filtering stage", prompt)
        self.assertNotIn("real emotional release points", prompt)
        self.assertIn('"decision":"keep"', prompt)
        self.assertIn('"decision":"reject"', prompt)
        self.assertIn("cand_demo_ep01_001", prompt)
        self.assertIn("expression_triggers", prompt)


class WorkflowExpressionTriggerPipelineTest(unittest.TestCase):
    def test_build_filter_frame_timestamps_expands_candidates_and_deduplicates(self) -> None:
        timestamps = build_filter_frame_timestamps(
            candidates=[
                {"start_time": 5.0, "end_time": 9.0},
                {"start_time": 8.0, "end_time": 12.0},
            ],
            duration_sec=20.0,
            interval_sec=2.0,
            context_sec=2.0,
            max_frames=20,
        )

        self.assertEqual(timestamps, [3.0, 5.0, 7.0, 9.0, 11.0, 13.0])

    def test_build_filter_frame_timestamps_respects_max_frames(self) -> None:
        timestamps = build_filter_frame_timestamps(
            candidates=[{"start_time": 0.0, "end_time": 20.0}],
            duration_sec=20.0,
            interval_sec=2.0,
            context_sec=0.0,
            max_frames=4,
        )

        self.assertEqual(timestamps, [0.0, 2.0, 4.0, 6.0])

    def test_parse_expression_trigger_candidates_filters_invalid_items(self) -> None:
        candidates = parse_expression_trigger_candidates(
            {
                "expression_candidates": [
                    {
                        "start_time": 5.0,
                        "end_time": 12.0,
                        "primary_expression": "爽到了",
                        "summary": "女主反击。",
                        "setup": "女主此前被压制。",
                        "turning_point": "女主开始反击。",
                        "expression_release": "压抑后的反击可能让观众感到解气。",
                        "candidate_reason": "可能是压抑后的反击。",
                    },
                    {
                        "start_time": 18.0,
                        "end_time": 20.0,
                        "primary_expression": "震惊",
                        "summary": "旧类型。",
                        "candidate_reason": "应过滤。",
                    },
                    {
                        "start_time": 30.0,
                        "end_time": 29.0,
                        "primary_expression": "笑死",
                    },
                ]
            },
            video_id="demo_ep01",
            duration_sec=60.0,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["candidate_id"], "cand_demo_ep01_001")
        self.assertEqual(candidates[0]["primary_expression"], "爽到了")
        self.assertEqual(candidates[0]["setup"], "女主此前被压制。")
        self.assertEqual(candidates[0]["turning_point"], "女主开始反击。")
        self.assertEqual(candidates[0]["expression_release"], "压抑后的反击可能让观众感到解气。")

    def test_parse_expression_trigger_candidates_allows_empty_structure_fields(self) -> None:
        candidates = parse_expression_trigger_candidates(
            {
                "expression_candidates": [
                    {
                        "start_time": 5.0,
                        "end_time": 12.0,
                        "primary_expression": "笑死",
                        "summary": "角色说错话。",
                        "candidate_reason": "可能形成笑点。",
                    }
                ]
            },
            video_id="demo_ep01",
            duration_sec=60.0,
        )

        self.assertEqual(candidates[0]["setup"], "")
        self.assertEqual(candidates[0]["turning_point"], "")
        self.assertEqual(candidates[0]["expression_release"], "")

    def test_consolidate_expression_triggers_removes_weak_and_nearby_same_expression_duplicates(self) -> None:
        triggers = [
            {
                "trigger_id": "t1",
                "start_time": 140.0,
                "end_time": 180.0,
                "cue_time": 170.0,
                "primary_expression": "看哭了",
                "intensity": 0.66,
                "confidence": 0.78,
            },
            {
                "trigger_id": "t2",
                "start_time": 195.0,
                "end_time": 243.0,
                "cue_time": 215.0,
                "primary_expression": "看哭了",
                "intensity": 0.84,
                "confidence": 0.9,
            },
            {
                "trigger_id": "t3",
                "start_time": 255.0,
                "end_time": 267.0,
                "cue_time": 262.0,
                "primary_expression": "看哭了",
                "intensity": 0.58,
                "confidence": 0.7,
            },
            {
                "trigger_id": "t4",
                "start_time": 275.0,
                "end_time": 295.0,
                "cue_time": 277.0,
                "primary_expression": "笑死",
                "intensity": 0.86,
                "confidence": 0.92,
            },
        ]

        consolidated = consolidate_expression_triggers(
            triggers,
            same_expression_gap_sec=30.0,
            min_intensity=0.6,
            min_confidence=0.72,
            max_triggers=None,
        )

        self.assertEqual([trigger["trigger_id"] for trigger in consolidated], ["t2", "t4"])

    def test_workflow_generates_candidates_with_10_second_frames_then_filters_to_triggers(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []
                self.last_call_diagnostics: dict[str, object] = {}

            def generate_json_multimodal(
                self,
                *,
                system_prompt: str,
                user_prompt: str,
                image_paths: list[Path],
                frame_timestamps_seconds: list[float] | None = None,
                max_tokens: int = 2400,
            ) -> dict[str, object]:
                self.calls.append(
                    {
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "image_paths": image_paths,
                        "frame_timestamps_seconds": frame_timestamps_seconds,
                        "max_tokens": max_tokens,
                    }
                )
                self.last_call_diagnostics = {"status": "success", "usage": {"total_tokens": 10 + len(self.calls)}}
                if len(self.calls) == 1:
                    return {
                        "expression_candidates": [
                            {
                                "start_time": 5.0,
                                "end_time": 12.0,
                                "primary_expression": "爽到了",
                                "summary": "女主反击。",
                                "setup": "女主此前被压制。",
                                "turning_point": "女主开始反击。",
                                "expression_release": "压抑后的反击可能让观众感到解气。",
                                "candidate_reason": "可能是压抑后的反击。",
                                "evidence_sources": ["subtitle", "frame"],
                            }
                        ]
                    }
                return {
                    "candidate_decisions": [
                        {
                            "candidate_id": "cand_demo_ep01_001",
                            "decision": "keep",
                            "primary_expression": "爽到了",
                            "decision_reason": "这是清晰反击点。",
                        }
                    ],
                    "expression_triggers": [
                        {
                            "start_time": 6.0,
                            "end_time": 9.0,
                            "cue_time": 8.0,
                            "source_type": "plot",
                            "primary_expression": "爽到了",
                            "intensity": 0.8,
                            "confidence": 0.9,
                            "summary": "女主反击成功。",
                            "setup": "女主此前被压制。",
                            "turning_point": "女主当前反击。",
                            "expression_release": "压抑释放形成爽感。",
                            "reason": "这是候选中的真实释放点。",
                        }
                    ]
                }

        class FakeExtraction:
            frame_count = 2

        extraction_calls: list[dict[str, object]] = []

        def fake_extract_frames(**kwargs: object) -> FakeExtraction:
            extraction_calls.append(kwargs)
            output_dir = kwargs["output_dir"]
            assert isinstance(output_dir, Path)
            for timestamp in kwargs["timestamps_seconds"]:
                output_dir.mkdir(parents=True, exist_ok=True)
                output_dir.joinpath(f"t_{int(round(float(timestamp) * 1000)):09d}.png").write_bytes(b"frame")
            return FakeExtraction()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text(
                "1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n\n"
                "2\n00:00:19,000 --> 00:00:20,000\n第二句\n",
                encoding="utf-8",
            )
            fake_client = FakeClient()
            with patch("pipelines.workflow_expression_trigger_detection.probe_video_duration_seconds", return_value=21.0), patch(
                "pipelines.workflow_expression_trigger_detection.extract_frames_at_timestamps",
                side_effect=fake_extract_frames,
            ):
                pipeline = WorkflowExpressionTriggerPipeline(llm_client=fake_client)
                result = pipeline.run(
                    video_id="demo_ep01",
                    video_file_path=video_path,
                    subtitle_file_path=subtitle_path,
                    metadata={"title": "Demo"},
                )

        self.assertEqual(extraction_calls[0]["timestamps_seconds"], [0.0, 10.0, 20.0])
        self.assertEqual(extraction_calls[0]["max_height"], 512)
        self.assertEqual(extraction_calls[1]["timestamps_seconds"], [3.0, 5.0, 7.0, 9.0, 11.0, 13.0])
        self.assertEqual(extraction_calls[1]["max_height"], 512)
        self.assertEqual(len(fake_client.calls), 2)
        self.assertEqual(fake_client.calls[0]["frame_timestamps_seconds"], [0.0, 10.0, 20.0])
        self.assertEqual(fake_client.calls[1]["frame_timestamps_seconds"], [3.0, 5.0, 7.0, 9.0, 11.0, 13.0])
        self.assertGreater(len(fake_client.calls[1]["image_paths"]), 0)
        self.assertIn("Find candidate story intervals in a short-drama episode where viewers may naturally want to react immediately.", str(fake_client.calls[0]["user_prompt"]))
        self.assertIn("Review the provided candidate story intervals and keep only the moments where viewers would actually want to react immediately.", str(fake_client.calls[1]["user_prompt"]))
        self.assertIn("女主此前被压制。", str(fake_client.calls[1]["user_prompt"]))
        self.assertEqual(len(result.expression_candidates), 1)
        self.assertEqual(result.candidate_decisions[0]["decision"], "keep")
        self.assertEqual(result.expression_candidates[0]["setup"], "女主此前被压制。")
        self.assertEqual(result.expression_triggers[0]["primary_expression"], "爽到了")
        self.assertEqual(result.llm_calls["candidate_generation"]["usage"]["total_tokens"], 11)
        self.assertEqual(result.llm_calls["candidate_filtering"]["usage"]["total_tokens"], 12)


if __name__ == "__main__":
    unittest.main()

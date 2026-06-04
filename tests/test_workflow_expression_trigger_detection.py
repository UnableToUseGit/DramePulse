from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipelines.client import LlmResponseError
from pipelines.workflow_expression_trigger_detection import (
    WorkflowExpressionTriggerPipeline,
    _build_candidate_generation_prompt,
    _build_candidate_filter_prompt,
    build_candidate_generation_frame_timestamps,
    build_resonance_cues,
    build_filter_frame_timestamps,
    build_visual_candidate_windows,
    consolidate_expression_triggers,
    parse_expression_trigger_candidates,
)


class WorkflowExpressionTriggerPromptTest(unittest.TestCase):
    def test_workflow_imports_from_new_package(self) -> None:
        from pipelines.expression_trigger.workflow import WorkflowExpressionTriggerPipeline

        self.assertIsNotNone(WorkflowExpressionTriggerPipeline)

    def test_workflow_helpers_import_from_new_package(self) -> None:
        from pipelines.expression_trigger.candidates import build_visual_candidate_windows
        from pipelines.expression_trigger.postprocess import consolidate_expression_triggers
        from pipelines.expression_trigger.resonance import build_resonance_cues
        from pipelines.expression_trigger.review import build_filter_frame_timestamps

        self.assertIsNotNone(build_visual_candidate_windows)
        self.assertIsNotNone(build_filter_frame_timestamps)
        self.assertIsNotNone(consolidate_expression_triggers)
        self.assertIsNotNone(build_resonance_cues)
        self.assertEqual(build_visual_candidate_windows.__module__, "pipelines.expression_trigger.candidates")
        self.assertEqual(build_filter_frame_timestamps.__module__, "pipelines.expression_trigger.review")
        self.assertEqual(consolidate_expression_triggers.__module__, "pipelines.expression_trigger.postprocess")
        self.assertEqual(build_resonance_cues.__module__, "pipelines.expression_trigger.resonance")

    def test_candidate_generation_prompt_is_high_recall_and_multimodal(self) -> None:
        prompt = _build_candidate_generation_prompt(
            video_id="demo_ep01",
            video_duration_seconds=120.0,
            subtitles_timeline="[5.000-8.000] 你终于输了",
            metadata={"title": "第 1 集"},
            frame_timestamps_seconds=[0.0, 10.0, 20.0],
            visual_candidate_windows=[
                {"start_time": 90.0, "end_time": 110.0, "reason": "low_dialogue_density"},
            ],
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
        self.assertIn("### 爽点", prompt)
        self.assertIn("### 甜点", prompt)
        self.assertIn("### 泪点", prompt)
        self.assertIn("### 笑点", prompt)
        self.assertIn("## VISUAL_CANDIDATE_WINDOWS", prompt)
        self.assertIn('"reason":"low_dialogue_density"', prompt)
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
                    "primary_expression": "爽点",
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
        self.assertIn("role_in_arc", prompt)
        self.assertIn("payoff_time", prompt)
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
                        "primary_expression": "爽点",
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
                        "primary_expression": "笑点",
                    },
                ]
            },
            video_id="demo_ep01",
            duration_sec=60.0,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["candidate_id"], "cand_demo_ep01_001")
        self.assertEqual(candidates[0]["primary_expression"], "爽点")
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
                        "primary_expression": "笑点",
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
                "primary_expression": "泪点",
                "intensity": 0.66,
                "confidence": 0.78,
            },
            {
                "trigger_id": "t2",
                "start_time": 195.0,
                "end_time": 243.0,
                "cue_time": 215.0,
                "primary_expression": "泪点",
                "intensity": 0.84,
                "confidence": 0.9,
            },
            {
                "trigger_id": "t3",
                "start_time": 255.0,
                "end_time": 267.0,
                "cue_time": 262.0,
                "primary_expression": "泪点",
                "intensity": 0.58,
                "confidence": 0.7,
            },
            {
                "trigger_id": "t4",
                "start_time": 275.0,
                "end_time": 295.0,
                "cue_time": 277.0,
                "primary_expression": "笑点",
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

    def test_build_visual_candidate_windows_uses_only_fixed_low_density_windows(self) -> None:
        from pipelines.utils import SubtitleSegment

        windows = build_visual_candidate_windows(
            subtitle_segments=[
                SubtitleSegment(start=0.0, end=5.0, text="密集台词"),
                SubtitleSegment(start=20.0, end=22.0, text="一句话"),
            ],
            duration_sec=40.0,
            window_sec=10.0,
            min_window_sec=4.0,
            max_windows=6,
        )

        self.assertEqual(
            windows,
            [
                {"start_time": 10.0, "end_time": 20.0, "reason": "low_dialogue_density"},
                {"start_time": 20.0, "end_time": 30.0, "reason": "low_dialogue_density"},
                {"start_time": 30.0, "end_time": 40.0, "reason": "low_dialogue_density"},
            ],
        )

    def test_build_visual_candidate_windows_does_not_rescan_all_subtitles_per_window(self) -> None:
        from pipelines.utils import SubtitleSegment

        subtitle_segments = [
            SubtitleSegment(start=float(index * 2), end=float(index * 2 + 1), text=f"line {index}")
            for index in range(300)
        ]

        with patch("pipelines.expression_trigger.candidates._overlap_seconds") as overlap_seconds:
            overlap_seconds.side_effect = lambda start_a, end_a, start_b, end_b: max(
                0.0,
                min(end_a, end_b) - max(start_a, start_b),
            )
            build_visual_candidate_windows(
                subtitle_segments=subtitle_segments,
                duration_sec=1000.0,
                window_sec=10.0,
                min_window_sec=4.0,
                max_windows=4,
            )

        self.assertLess(overlap_seconds.call_count, 1000)

    def test_build_visual_candidate_windows_terminates_when_duration_has_sub_millisecond_tail(self) -> None:
        from pipelines.utils import SubtitleSegment

        subtitle_segments = [
            SubtitleSegment(start=0.0, end=196.245011, text="full coverage"),
        ]

        overlap_call_count = 0

        def overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
            nonlocal overlap_call_count
            overlap_call_count += 1
            if overlap_call_count > 100:
                raise AssertionError("build_visual_candidate_windows did not terminate")
            return max(0.0, min(end_a, end_b) - max(start_a, start_b))

        with patch("pipelines.expression_trigger.candidates._overlap_seconds", side_effect=overlap_seconds):
            windows = build_visual_candidate_windows(
                subtitle_segments=subtitle_segments,
                duration_sec=196.245011,
                window_sec=15.0,
                min_window_sec=4.0,
                max_windows=4,
            )

        self.assertEqual(windows, [])

    def test_build_candidate_generation_frame_timestamps_densely_samples_visual_windows(self) -> None:
        timestamps = build_candidate_generation_frame_timestamps(
            duration_sec=40.0,
            sample_interval_sec=10.0,
            max_frames=None,
            visual_candidate_windows=[
                {"start_time": 9.5, "end_time": 13.5, "reason": "low_dialogue_density"},
                {"start_time": 30.0, "end_time": 34.0, "reason": "low_dialogue_density"},
            ],
            visual_window_sample_interval_sec=1.0,
            visual_window_max_frames=None,
        )

        self.assertEqual(timestamps, [0.0, 9.5, 10.5, 11.5, 12.5, 20.0, 30.0, 31.0, 32.0, 33.0])

    def test_build_candidate_generation_frame_timestamps_resamples_global_frames_after_excluding_visual_windows(self) -> None:
        timestamps = build_candidate_generation_frame_timestamps(
            duration_sec=100.0,
            sample_interval_sec=10.0,
            max_frames=3,
            visual_candidate_windows=[
                {"start_time": 40.0, "end_time": 60.0, "reason": "low_dialogue_density"},
            ],
            visual_window_sample_interval_sec=10.0,
            visual_window_max_frames=None,
        )

        self.assertEqual(timestamps, [0.0, 40.0, 50.0, 60.0, 90.0])

    def test_build_resonance_cues_maps_payoff_to_frontend_fields(self) -> None:
        cues = build_resonance_cues(
            [
                {
                    "trigger_id": "et_demo_ep01_001",
                    "video_id": "demo_ep01",
                    "payoff_time": 40.0,
                    "start_time": 35.0,
                    "end_time": 43.0,
                    "primary_expression": "泪点",
                    "intensity": 0.8,
                    "confidence": 0.9,
                    "summary": "母亲转悲为喜。",
                },
                {
                    "trigger_id": "et_demo_ep01_002",
                    "video_id": "demo_ep01",
                    "payoff_time": 80.0,
                    "start_time": 78.0,
                    "end_time": 82.0,
                    "primary_expression": "笑点",
                    "intensity": 0.7,
                    "confidence": 0.8,
                    "summary": "包袱落点。",
                },
            ],
            duration_sec=100.0,
        )

        self.assertEqual(cues[0]["cue_id"], "res_demo_ep01_001")
        self.assertEqual(cues[0]["source_trigger_id"], "et_demo_ep01_001")
        self.assertEqual(cues[0]["emotion_type"], "泪点")
        self.assertEqual(cues[0]["label"], "泪目了")
        self.assertEqual(cues[0]["ui_trigger_time"], 41.5)
        self.assertEqual(cues[0]["duration_sec"], 6.0)
        self.assertEqual(cues[1]["emotion_type"], "笑点")
        self.assertEqual(cues[1]["ui_trigger_time"], 80.2)

    def test_workflow_generates_candidates_with_dense_visual_window_frames_then_filters_to_triggers(self) -> None:
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
                                "primary_expression": "爽点",
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
                            "primary_expression": "爽点",
                            "role_in_arc": "payoff",
                            "payoff_time": 8.0,
                            "payoff_reason": "反击已经落地。",
                            "decision_reason": "这是清晰反击点。",
                        }
                    ],
                    "expression_triggers": [
                        {
                            "start_time": 6.0,
                            "end_time": 9.0,
                            "payoff_time": 8.0,
                            "source_type": "plot",
                            "primary_expression": "爽点",
                            "candidate_id": "cand_demo_ep01_001",
                            "decision": "keep",
                            "role_in_arc": "payoff",
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
            with patch("pipelines.expression_trigger.workflow.probe_video_duration_seconds", return_value=21.0), patch(
                "pipelines.expression_trigger.workflow.extract_frames_at_timestamps",
                side_effect=fake_extract_frames,
            ):
                progress_events: list[tuple[str, dict[str, object]]] = []
                pipeline = WorkflowExpressionTriggerPipeline(
                    llm_client=fake_client,
                    progress_callback=lambda event, payload: progress_events.append((event, payload)),
                )
                result = pipeline.run(
                    video_id="demo_ep01",
                    video_file_path=video_path,
                    subtitle_file_path=subtitle_path,
                    metadata={"title": "Demo"},
                )

        self.assertEqual(
            extraction_calls[0]["timestamps_seconds"],
            [0.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0],
        )
        self.assertEqual(extraction_calls[0]["max_height"], 512)
        self.assertEqual(extraction_calls[1]["timestamps_seconds"], [3.0, 5.0, 7.0, 9.0, 11.0, 13.0])
        self.assertEqual(extraction_calls[1]["max_height"], 512)
        self.assertEqual(len(fake_client.calls), 2)
        self.assertEqual(
            fake_client.calls[0]["frame_timestamps_seconds"],
            [0.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0],
        )
        self.assertEqual(fake_client.calls[1]["frame_timestamps_seconds"], [3.0, 5.0, 7.0, 9.0, 11.0, 13.0])
        self.assertGreater(len(fake_client.calls[1]["image_paths"]), 0)
        self.assertIn("Find candidate story intervals in a short-drama episode where viewers may naturally want to react immediately.", str(fake_client.calls[0]["user_prompt"]))
        self.assertIn("Review the provided candidate story intervals and keep only the moments where viewers would actually want to react immediately.", str(fake_client.calls[1]["user_prompt"]))
        self.assertIn("女主此前被压制。", str(fake_client.calls[1]["user_prompt"]))
        self.assertEqual(len(result.expression_candidates), 1)
        self.assertEqual(result.candidate_decisions[0]["decision"], "keep")
        self.assertEqual(result.expression_candidates[0]["setup"], "女主此前被压制。")
        self.assertEqual(result.expression_triggers[0]["primary_expression"], "爽点")
        self.assertEqual(result.expression_triggers[0]["candidate_id"], "cand_demo_ep01_001")
        self.assertEqual(result.expression_triggers[0]["payoff_time"], 8.0)
        self.assertEqual(result.resonance_cues[0]["emotion_type"], "爽点")
        self.assertEqual(result.resonance_cues[0]["ui_trigger_time"], 8.5)
        self.assertEqual(result.llm_calls["candidate_generation"]["usage"]["total_tokens"], 11)
        self.assertEqual(result.llm_calls["candidate_filtering"]["usage"]["total_tokens"], 12)
        self.assertEqual([event for event, _payload in progress_events], [
            "preprocess_subtitles_loaded",
            "preprocess_duration_probed",
            "preprocess_visual_windows_start",
            "preprocess_visual_windows_done",
            "preprocess_candidate_frames_built",
            "prepared",
            "candidate_frames_extracted",
            "candidate_generation_start",
            "candidate_generation_done",
            "filter_frames_extracted",
            "candidate_filtering_start",
            "candidate_filtering_done",
            "completed",
        ])
        self.assertEqual(progress_events[0][1]["subtitle_segment_count"], 2)
        self.assertEqual(progress_events[1][1]["duration_sec"], 21.0)
        self.assertEqual(progress_events[2][1]["visual_candidate_window_sec"], 10.0)
        self.assertEqual(progress_events[3][1]["visual_window_count"], 1)
        self.assertEqual(progress_events[4][1]["candidate_frame_count"], 12)
        self.assertEqual(progress_events[5][1]["visual_window_count"], 1)
        self.assertEqual(progress_events[5][1]["candidate_frame_count"], 12)
        self.assertEqual(
            progress_events[5][1]["visual_candidate_windows"],
            [
                {"start_time": 10.0, "end_time": 20.0, "reason": "low_dialogue_density"},
            ],
        )
        self.assertEqual(progress_events[6][1]["extracted_frame_count"], 2)
        self.assertEqual(progress_events[8][1]["candidate_count"], 1)
        self.assertEqual(progress_events[9][1]["filter_frame_count"], 6)
        self.assertEqual(progress_events[-1][1]["trigger_count"], 1)
        self.assertEqual(progress_events[-1][1]["resonance_cue_count"], 1)

    def test_workflow_preserves_candidate_generation_diagnostics_when_llm_fails(self) -> None:
        class FakeClient:
            last_call_diagnostics = {
                "status": "failed",
                "provider": "volc_ark",
                "model": "doubao-test",
                "error_type": "LlmResponseError",
                "error": "LLM response has unexpected shape: str",
                "response_type": "str",
                "raw_response_text": "raw ark response",
            }

            def generate_json_multimodal(self, **kwargs: object) -> dict[str, object]:
                raise LlmResponseError("LLM response has unexpected shape: str", raw_response_text="raw ark response")

        class FakeExtraction:
            frame_count = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text("1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n", encoding="utf-8")
            pipeline = WorkflowExpressionTriggerPipeline(llm_client=FakeClient())

            with patch("pipelines.expression_trigger.workflow.probe_video_duration_seconds", return_value=10.0), patch(
                "pipelines.expression_trigger.workflow.extract_frames_at_timestamps",
                return_value=FakeExtraction(),
            ), self.assertRaises(LlmResponseError):
                pipeline.run(
                    video_id="demo_ep01",
                    video_file_path=video_path,
                    subtitle_file_path=subtitle_path,
                )

        self.assertEqual(pipeline.last_llm_call["candidate_generation"]["status"], "failed")
        self.assertEqual(pipeline.last_llm_call["candidate_generation"]["response_type"], "str")
        self.assertEqual(pipeline.last_llm_call["candidate_generation"]["raw_response_text"], "raw ark response")
        self.assertEqual(pipeline.last_llm_call["candidate_filtering"], {})


if __name__ == "__main__":
    unittest.main()

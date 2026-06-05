from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter.baseline_text import Utterance
from pipelines.story_chapter.workflow import (
    BoundaryCandidate,
    ChapterSelectionConstraints,
    StoryChapterWorkflowPipeline,
    build_selector_user_prompt,
    parse_and_validate_selector_result,
    recall_boundary_candidates,
    score_topic_shifts_with_llm,
)


class FakeWorkflowClient:
    def __init__(self, payload: dict[str, object] | list[dict[str, object]]) -> None:
        self.payloads = payload if isinstance(payload, list) else [payload]
        self.payload = self.payloads[-1]
        self.calls: list[dict[str, object]] = []

    def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, **kwargs})
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        return self.payloads[index]


class StoryChapterWorkflowTest(unittest.TestCase):
    def test_recall_boundary_candidates_uses_scene_pause_and_density_signals(self) -> None:
        utterances = [
            Utterance("u_001", 0.5, 2.0, "你到底是谁？"),
            Utterance("u_002", 2.2, 3.0, "我只是路过。"),
            Utterance("u_003", 5.2, 6.0, "合同已经签了。"),
            Utterance("u_004", 6.1, 6.8, "现在开始执行。"),
            Utterance("u_005", 7.0, 7.5, "走。"),
        ]
        scenes = [
            {"scene_id": "s_001", "start_time": 0.0, "end_time": 5.0},
            {"scene_id": "s_002", "start_time": 5.0, "end_time": 9.0},
        ]

        candidates = recall_boundary_candidates(
            utterances=utterances,
            scenes=scenes,
            video_duration_seconds=10.0,
            pause_threshold_seconds=1.2,
            density_window_seconds=3.0,
            merge_window_seconds=0.6,
        )

        self.assertGreaterEqual(len(candidates), 1)
        merged = candidates[0]
        self.assertEqual(merged.candidate_id, "bc_001")
        self.assertEqual(merged.time, 5.0)
        self.assertIn("scene_boundary", merged.signals)
        self.assertIn("long_pause", merged.signals)
        self.assertGreater(merged.rule_score, 0.0)
        self.assertEqual(merged.score, merged.rule_score)
        self.assertEqual(merged.evidence["gap_seconds"], 2.2)

    def test_score_topic_shifts_updates_candidate_scores(self) -> None:
        client = FakeWorkflowClient(
            {
                "topic_shift_reviews": [
                    {
                        "candidate_id": "bc_001",
                        "topic_shift_score": 0.9,
                        "reason": "身份质疑转为身份揭露。",
                    }
                ]
            }
        )
        candidate = BoundaryCandidate(
            candidate_id="bc_001",
            time=5.0,
            rule_score=0.4,
            score=0.4,
            signals=["scene_boundary"],
            evidence={},
        )

        scored, warnings, raw = score_topic_shifts_with_llm(
            llm_client=client,
            video_id="demo_ep01",
            video_duration_seconds=10.0,
            utterances=[
                Utterance("u_001", 0.0, 1.0, "你是谁？"),
                Utterance("u_002", 5.0, 6.0, "我是继承人。"),
            ],
            candidates=[candidate],
        )

        self.assertEqual(warnings, [])
        self.assertEqual(raw, client.payload)
        self.assertEqual(scored[0].topic_shift_score, 0.9)
        self.assertEqual(scored[0].topic_shift_reason, "身份质疑转为身份揭露。")
        self.assertGreater(scored[0].score, candidate.score)
        self.assertIn("bc_001", client.calls[0]["user_prompt"])
        self.assertIn("你是谁？", client.calls[0]["user_prompt"])

    def test_score_topic_shifts_retries_when_response_misses_candidates(self) -> None:
        client = FakeWorkflowClient(
            [
                {
                    "candidate_id": "bc_001",
                    "topic_shift_score": 0.1,
                    "reason": "仍是同一事件。",
                },
                {
                    "topic_shift_reviews": [
                        {"candidate_id": "bc_001", "topic_shift_score": 0.1, "reason": "仍是同一事件。"},
                        {"candidate_id": "bc_002", "topic_shift_score": 0.9, "reason": "进入新事件。"},
                    ]
                },
            ]
        )
        candidates = [
            BoundaryCandidate("bc_001", 5.0, 0.4, 0.4, ["scene_boundary"], {}),
            BoundaryCandidate("bc_002", 10.0, 0.4, 0.4, ["scene_boundary"], {}),
        ]

        scored, warnings, raw = score_topic_shifts_with_llm(
            llm_client=client,
            video_id="demo_ep01",
            video_duration_seconds=20.0,
            utterances=[
                Utterance("u_001", 0.0, 1.0, "讨薪。"),
                Utterance("u_002", 9.0, 10.0, "回家。"),
            ],
            candidates=candidates,
        )

        self.assertEqual(len(client.calls), 2)
        self.assertIn("missed candidate ids: bc_002", client.calls[1]["user_prompt"])
        self.assertEqual(raw, client.payloads[1])
        self.assertEqual([candidate.topic_shift_score for candidate in scored], [0.1, 0.9])
        self.assertTrue(any("retry" in warning.lower() for warning in warnings))

    def test_parse_selector_result_requires_candidate_boundaries_and_full_coverage(self) -> None:
        candidates = [
            BoundaryCandidate(
                candidate_id="bc_001",
                time=5.0,
                rule_score=0.8,
                score=0.8,
                signals=["scene_boundary"],
                evidence={},
            )
        ]

        chapters, warnings = parse_and_validate_selector_result(
            raw={
                "chapters": [
                    {
                        "start_time": 0.0,
                        "end_time": 5.0,
                        "end_boundary_candidate_id": "bc_001",
                        "title": "身份遭疑",
                        "summary": "众人质疑身份。",
                        "importance": 0.7,
                    },
                    {
                        "start_time": 5.0,
                        "end_time": 10.0,
                        "end_boundary_candidate_id": None,
                        "title": "身份揭露",
                        "summary": "身份揭开。",
                        "importance": 0.9,
                    },
                ]
            },
            video_id="demo_ep01",
            video_duration_seconds=10.0,
            candidates=candidates,
        )

        self.assertEqual(warnings, [])
        self.assertEqual(chapters[0]["chapter_id"], "ch_demo_ep01_001")
        self.assertEqual(chapters[0]["video_id"], "demo_ep01")
        self.assertEqual(chapters[0]["start_time"], 0.0)
        self.assertEqual(chapters[-1]["end_time"], 10.0)
        self.assertEqual(chapters[0]["title"], "身份遭疑")

    def test_parse_selector_result_accepts_string_importance_labels(self) -> None:
        candidates = [
            BoundaryCandidate("bc_001", 5.0, 0.8, 0.8, ["scene_boundary"], {}),
        ]

        chapters, warnings = parse_and_validate_selector_result(
            raw={
                "chapters": [
                    {
                        "start_time": 0.0,
                        "end_time": 5.0,
                        "end_boundary_candidate_id": "bc_001",
                        "title": "身份遭疑",
                        "summary": "众人质疑身份。",
                        "importance": "high",
                    },
                    {
                        "start_time": 5.0,
                        "end_time": 10.0,
                        "end_boundary_candidate_id": None,
                        "title": "身份揭露",
                        "summary": "身份揭开。",
                        "importance": "medium",
                    },
                ]
            },
            video_id="demo_ep01",
            video_duration_seconds=10.0,
            candidates=candidates,
        )

        self.assertEqual(warnings, [])
        self.assertEqual(chapters[0]["importance"], 0.85)
        self.assertEqual(chapters[1]["importance"], 0.6)

    def test_selector_prompt_enforces_duration_and_numeric_importance(self) -> None:
        prompt = build_selector_user_prompt(
            video_id="demo_ep01",
            video_duration_seconds=60.0,
            utterances=[Utterance("u_001", 1.0, 2.0, "开场。")],
            candidates=[BoundaryCandidate("bc_001", 20.0, 0.8, 0.8, ["scene_boundary"], {})],
            frame_timestamps_by_candidate={"bc_001": [19.0, 20.0, 21.0]},
            constraints=ChapterSelectionConstraints(min_chapter_seconds=12.0, max_chapters=8),
        )

        self.assertIn("Do not create chapters shorter than MIN_CHAPTER_SECONDS", prompt)
        self.assertIn("importance must be a number from 0 to 1", prompt)
        self.assertIn("Prefer 3 to 6 chapters", prompt)

    def test_workflow_pipeline_writes_candidate_selector_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            transcription_path = tmp_path / "video.transcription.json"
            scene_path = tmp_path / "scene_detection.json"
            output_root = tmp_path / "output"
            video_path.write_bytes(b"fake video")
            transcription_path.write_text(
                json.dumps(
                    {
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 0.0,
                                    "raw_result": {
                                        "transcripts": [
                                            {
                                                "sentences": [
                                                    {"begin_time": 500, "end_time": 2000, "text": "你到底是谁？"},
                                                    {"begin_time": 2200, "end_time": 3000, "text": "我只是路过。"},
                                                    {"begin_time": 5200, "end_time": 6000, "text": "我是继承人。"},
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            scene_path.write_text(
                json.dumps(
                    {
                        "video_id": "demo_ep01",
                        "duration_seconds": 10.0,
                        "scenes": [
                            {"scene_id": "s_001", "start_time": 0.0, "end_time": 5.0},
                            {"scene_id": "s_002", "start_time": 5.0, "end_time": 10.0},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            text_client = FakeWorkflowClient(
                {
                    "topic_shift_reviews": [
                        {"candidate_id": "bc_001", "topic_shift_score": 0.95, "reason": "身份疑问进入身份揭露。"}
                    ]
                }
            )
            selector_client = FakeWorkflowClient(
                {
                    "chapters": [
                        {
                            "start_time": 0.0,
                            "end_time": 5.0,
                            "end_boundary_candidate_id": "bc_001",
                            "title": "身份遭疑",
                            "summary": "众人质疑男主身份。",
                            "importance": 0.7,
                        },
                        {
                            "start_time": 5.0,
                            "end_time": 10.0,
                            "end_boundary_candidate_id": None,
                            "title": "身份揭露",
                            "summary": "男主说出继承人身份。",
                            "importance": 0.9,
                        },
                    ],
                    "rejected_candidates": [],
                    "warnings": [],
                }
            )

            def fake_extract_frames(
                *,
                video_path: Path,
                output_dir: Path,
                timestamps_seconds: list[float],
                max_height: int,
            ):
                output_dir.mkdir(parents=True, exist_ok=True)
                for timestamp in timestamps_seconds:
                    (output_dir / f"t_{int(timestamp * 1000):09d}.png").write_bytes(b"png")
                return {"backend": "fake", "frame_count": len(timestamps_seconds)}

            pipeline = StoryChapterWorkflowPipeline(
                text_llm_client=text_client,
                mllm_client=selector_client,
                extract_frames=fake_extract_frames,
                top_candidates=1,
                candidate_frame_offsets_seconds=(-1.0, 0.0, 1.0),
            )

            output_path = pipeline.run(
                video_id="demo_ep01",
                video_path=video_path,
                video_metadata={"duration_seconds": 10.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=output_root,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["generation_mode"], "workflow_candidate_mllm_selector")
        self.assertGreaterEqual(len(payload["boundary_candidates"]), 1)
        self.assertEqual(payload["story_chapters"][0]["title"], "身份遭疑")
        self.assertIn("FULL_UTTERANCE_TIMELINE", selector_client.calls[0]["user_prompt"])
        self.assertLessEqual(len(selector_client.calls[0]["image_paths"]), 3)

    def test_workflow_pipeline_reports_progress_stages(self) -> None:
        messages: list[str] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            transcription_path = tmp_path / "video.transcription.json"
            scene_path = tmp_path / "scene_detection.json"
            video_path.write_bytes(b"fake video")
            transcription_path.write_text(
                json.dumps(
                    {
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 0.0,
                                    "raw_result": {
                                        "transcripts": [
                                            {
                                                "sentences": [
                                                    {"begin_time": 500, "end_time": 1500, "text": "开场。"},
                                                    {"begin_time": 3500, "end_time": 4500, "text": "转场。"},
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            scene_path.write_text(
                json.dumps(
                    {
                        "video_id": "demo_ep01",
                        "duration_seconds": 8.0,
                        "scenes": [
                            {"scene_id": "s_001", "start_time": 0.0, "end_time": 3.0},
                            {"scene_id": "s_002", "start_time": 3.0, "end_time": 8.0},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            def fake_extract_frames(**kwargs):
                output_dir = kwargs["output_dir"]
                output_dir.mkdir(parents=True, exist_ok=True)
                for timestamp in kwargs["timestamps_seconds"]:
                    (output_dir / f"t_{int(timestamp * 1000):09d}.png").write_bytes(b"png")
                return {"backend": "fake", "frame_count": len(kwargs["timestamps_seconds"])}

            pipeline = StoryChapterWorkflowPipeline(
                text_llm_client=FakeWorkflowClient(
                    {"topic_shift_reviews": [{"candidate_id": "bc_001", "topic_shift_score": 0.8, "reason": "转场。"}]}
                ),
                mllm_client=FakeWorkflowClient(
                    {
                        "chapters": [
                            {
                                "start_time": 0.0,
                                "end_time": 8.0,
                                "end_boundary_candidate_id": None,
                                "title": "剧情开场",
                                "summary": "故事开始并转场。",
                                "importance": 0.6,
                            }
                        ],
                        "warnings": [],
                    }
                ),
                extract_frames=fake_extract_frames,
                top_candidates=1,
                progress_logger=messages.append,
            )
            pipeline.run(
                video_id="demo_ep01",
                video_path=video_path,
                video_metadata={"duration_seconds": 8.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=tmp_path / "output",
            )

        joined = "\n".join(messages)
        self.assertIn("load inputs", joined)
        self.assertIn("topic shift LLM start", joined)
        self.assertIn("frame extraction start", joined)
        self.assertIn("MLLM selector start", joined)
        self.assertIn("wrote output", joined)


if __name__ == "__main__":
    unittest.main()

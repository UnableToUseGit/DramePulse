from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter.baseline_text import Utterance
from pipelines.story_chapter.workflow import (
    BoundaryCandidate,
    StoryChapterWorkflowPipeline,
    parse_and_validate_selector_result,
    recall_boundary_candidates,
    score_topic_shifts_with_llm,
)


class FakeWorkflowClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, **kwargs})
        return self.payload


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


if __name__ == "__main__":
    unittest.main()

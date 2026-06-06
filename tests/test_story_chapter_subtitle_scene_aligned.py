from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter.baseline_text import Utterance
from pipelines.story_chapter.subtitle_scene_aligned import (
    StoryChapterSubtitleSceneAlignedPipeline,
    align_draft_chapters_to_scene_boundaries,
    boundary_frame_timestamps,
    build_boundary_review_user_prompt,
    build_draft_chapter_user_prompt,
    parse_boundary_reviews,
    parse_draft_chapters,
    select_boundary_candidates,
)


class FakeSubtitleSceneClient:
    def __init__(self, *payloads: dict[str, object]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict[str, object]] = []

    def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, **kwargs})
        return self.payloads.pop(0)


class StoryChapterSubtitleSceneAlignedTest(unittest.TestCase):
    def test_prompt_includes_speaker_id_and_parse_keeps_boundary_reasons(self) -> None:
        prompt = build_draft_chapter_user_prompt(
            video_id="demo_ep01",
            video_duration_seconds=12.0,
            utterances=[
                Utterance(
                    utterance_id="u_001",
                    start_time=0.5,
                    end_time=1.2,
                    text="你是谁？",
                    speaker_id="speaker_a",
                )
            ],
        )
        self.assertIn("speaker=speaker_a", prompt)

        drafts, warnings = parse_draft_chapters(
            {
                "chapters": [
                    {
                        "start_utterance_id": "u_001",
                        "start_time": 0.5,
                        "start_reason": "这是新冲突的第一句台词。",
                        "end_utterance_id": "u_002",
                        "end_time": 7.8,
                        "end_reason": "这句台词完成了本章冲突。",
                        "title": "开场冲突",
                        "summary": "众人发生争执。",
                        "reason": "该范围构成一个完整冲突。",
                    }
                ]
            }
        )

        self.assertEqual(warnings, [])
        self.assertEqual(drafts[0].start_reason, "这是新冲突的第一句台词。")
        self.assertEqual(drafts[0].end_reason, "这句台词完成了本章冲突。")

    def test_boundary_review_prompt_uses_subtitles_and_frames_without_candidate_list(self) -> None:
        chapters = [
            {
                "chapter_id": "ch_demo_001",
                "video_id": "demo",
                "start_time": 0.0,
                "end_time": 12.0,
                "title": "上章",
                "summary": "上一章摘要。",
                "reason": "上一章语义完整。",
            },
            {
                "chapter_id": "ch_demo_002",
                "video_id": "demo",
                "start_time": 10.0,
                "end_time": 30.0,
                "title": "下章",
                "summary": "下一章摘要。",
                "reason": "下一章语义开始。",
            },
        ]
        scenes = [
            {"scene_id": "s1", "start_time": 0.0, "end_time": 9.0},
            {"scene_id": "s2", "start_time": 9.0, "end_time": 15.0},
            {"scene_id": "s3", "start_time": 15.0, "end_time": 30.0},
        ]

        candidates = select_boundary_candidates(
            previous_chapter=chapters[0],
            next_chapter=chapters[1],
            scenes=scenes,
            video_duration_seconds=30.0,
        )
        subtitle_context = [
            Utterance("u_001", 8.5, 9.5, "上一章最后一句。", "speaker_a"),
            Utterance("u_002", 14.5, 15.5, "下一章第一句。", "speaker_b"),
        ]
        prompt = build_boundary_review_user_prompt(
            video_id="demo",
            boundary_review={
                "boundary_id": "br_001",
                "previous_chapter": chapters[0],
                "next_chapter": chapters[1],
                "candidates": candidates,
                "previous_chapter_subtitles": [subtitle_context[0]],
                "next_chapter_subtitles": [subtitle_context[1]],
                "subtitle_context": subtitle_context,
                "subtitle_context_time_range": {"start_time": 2.0, "end_time": 22.0},
                "search_time_range": {"start_time": 2.0, "end_time": 22.0},
            },
            frame_timestamps_seconds=[9.0, 15.0],
        )
        reviews, warnings = parse_boundary_reviews(
            {"boundary_reviews": [{"boundary_id": "br_001", "boundary_time": 15.0, "reason": "15 秒是视觉转场。"}]},
            valid_boundary_ids={"br_001"},
            frame_times_by_boundary={"br_001": {9.0, 15.0}},
        )

        self.assertEqual([candidate["time"] for candidate in candidates], [9.0, 11.0, 15.0])
        self.assertIn("PREVIOUS_CHAPTER_SUBTITLES", prompt)
        self.assertIn("NEXT_CHAPTER_SUBTITLES", prompt)
        self.assertNotIn("CANDIDATE_BOUNDARIES", prompt)
        self.assertNotIn("title:", prompt)
        self.assertNotIn("summary:", prompt)
        self.assertIn("BOUNDARY_SUBTITLE_CONTEXT", prompt)
        self.assertIn("u_001 [8.500-9.500] speaker=speaker_a: 上一章最后一句。", prompt)
        self.assertIn("u_002 [14.500-15.500] speaker=speaker_b: 下一章第一句。", prompt)
        self.assertEqual(warnings, [])
        self.assertEqual(reviews[0]["boundary_time"], 15.0)
        self.assertEqual(reviews[0]["reason"], "15 秒是视觉转场。")
        timestamps, by_boundary = boundary_frame_timestamps(
            [{"boundary_id": "br_001", "search_time_range": {"start_time": 2.0, "end_time": 5.0}}],
            video_duration_seconds=30.0,
        )
        self.assertEqual(timestamps, [2.0, 3.0, 4.0, 5.0])
        self.assertEqual(by_boundary["br_001"], timestamps)

    def test_align_draft_chapters_aligns_subtitle_ranges_to_scene_ranges(self) -> None:
        drafts, warnings = parse_draft_chapters(
            {
                "chapters": [
                    {
                        "start_utterance_id": "u_001",
                        "start_time": 1.16,
                        "end_utterance_id": "u_018",
                        "end_time": 84.0,
                        "title": "结清工钱",
                        "summary": "讨薪事件完成。",
                        "reason": "讨薪目标已经完成。",
                    },
                    {
                        "start_utterance_id": "u_019",
                        "start_time": 95.0,
                        "end_utterance_id": "u_024",
                        "end_time": 136.0,
                        "title": "汇款报平安",
                        "summary": "汇款后接到电话。",
                        "reason": "剧情转入汇款返乡。",
                    },
                ]
            }
        )

        chapters, align_warnings = align_draft_chapters_to_scene_boundaries(
            video_id="beiwang_ep01",
            video_duration_seconds=301.133,
            scenes=[
                {"scene_id": "s1", "start_time": 0.0, "end_time": 63.233},
                {"scene_id": "s2", "start_time": 63.233, "end_time": 83.533},
                {"scene_id": "s3", "start_time": 83.533, "end_time": 85.8},
                {"scene_id": "s4", "start_time": 85.8, "end_time": 90.0},
                {"scene_id": "s5", "start_time": 90.0, "end_time": 136.833},
                {"scene_id": "s6", "start_time": 136.833, "end_time": 249.1},
                {"scene_id": "s7", "start_time": 249.1, "end_time": 301.133},
            ],
            drafts=drafts,
            max_alignment_window_seconds=8.0,
            min_chapter_seconds=12.0,
        )

        self.assertEqual(warnings, [])
        self.assertEqual(align_warnings, [])
        self.assertEqual(
            [(chapter["start_time"], chapter["end_time"]) for chapter in chapters],
            [(0.0, 85.8), (90.0, 136.833)],
        )
        self.assertEqual(chapters[0]["title"], "结清工钱")
        self.assertEqual(chapters[1]["alignment"]["subtitle_start_time"], 95.0)
        self.assertEqual(chapters[1]["alignment"]["subtitle_end_time"], 136.0)
        self.assertEqual(chapters[1]["reason"], "剧情转入汇款返乡。")

    def test_pipeline_uses_mllm_boundary_reviews_for_final_continuous_chapters(self) -> None:
        subtitle_payload = {
            "chapters": [
                {
                    "start_utterance_id": "u_001",
                    "start_time": 2.5,
                    "end_utterance_id": "u_001",
                    "end_time": 3.2,
                    "title": "开场冲突",
                    "summary": "众人发生争执。",
                    "reason": "第一句台词建立冲突。",
                },
                {
                    "start_utterance_id": "u_002",
                    "start_time": 7.0,
                    "end_utterance_id": "u_002",
                    "end_time": 7.8,
                    "title": "冲突收束",
                    "summary": "冲突暂时结束。",
                    "reason": "第二句台词结束冲突。",
                },
            ]
        }
        boundary_payload = {
            "boundary_reviews": [
                {
                    "boundary_id": "br_001",
                    "boundary_time": 6.0,
                    "reason": "6 秒是骑车过场结束并进入下一段冲突的转场。",
                }
            ]
        }
        client = FakeSubtitleSceneClient(subtitle_payload, boundary_payload)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            transcription_path = root / "video.transcription.json"
            scene_path = root / "scene_detection.json"
            video_path = root / "video.mp4"
            video_path.write_bytes(b"video")
            transcription_path.write_text(
                json.dumps(
                    {
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 0,
                                    "raw_result": {
                                        "transcripts": [
                                            {
                                                "sentences": [
                                                    {"begin_time": 2500, "end_time": 3200, "text": "你是谁？"},
                                                    {"begin_time": 7000, "end_time": 7800, "text": "事情结束了。"},
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            scene_path.write_text(
                json.dumps(
                    {
                        "scenes": [
                            {"scene_id": "s1", "start_time": 0.0, "end_time": 2.0},
                            {"scene_id": "s2", "start_time": 2.0, "end_time": 4.0},
                            {"scene_id": "s3", "start_time": 4.0, "end_time": 6.0},
                            {"scene_id": "s4", "start_time": 6.0, "end_time": 8.0},
                            {"scene_id": "s5", "start_time": 8.0, "end_time": 12.0},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            frame_calls: list[dict[str, object]] = []

            def fake_extract_frames(**kwargs):
                frame_calls.append(kwargs)
                output_dir = Path(kwargs["output_dir"])
                output_dir.mkdir(parents=True, exist_ok=True)
                for index, _timestamp in enumerate(kwargs["timestamps_seconds"], start=1):
                    (output_dir / f"frame_{index:03d}.png").write_bytes(b"png")
                return {"backend": "fake", "frame_count": len(kwargs["timestamps_seconds"])}

            output_path = StoryChapterSubtitleSceneAlignedPipeline(
                llm_client=client,
                extract_frames=fake_extract_frames,
                min_chapter_seconds=3.0,
            ).run(
                video_id="demo_ep01",
                video_path=video_path,
                video_metadata={"duration_seconds": 12.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=root / "output",
            )
            output = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(output["generation_mode"], "subtitle_scene_aligned")
        self.assertEqual(
            [(chapter["start_time"], chapter["end_time"], chapter["title"]) for chapter in output["story_chapters"]],
            [(0.0, 6.0, "开场冲突"), (6.0, 12.0, "冲突收束")],
        )
        self.assertEqual(output["boundary_reviews"][0]["boundary_time"], 6.0)
        self.assertEqual(output["boundary_reviews"][0]["reason"], "6 秒是骑车过场结束并进入下一段冲突的转场。")
        self.assertEqual(output["subtitle_chapters"][0]["reason"], "第一句台词建立冲突。")
        self.assertEqual(len(client.calls), 2)
        self.assertIn("PREVIOUS_CHAPTER_SUBTITLES", client.calls[1]["user_prompt"])
        self.assertIn("NEXT_CHAPTER_SUBTITLES", client.calls[1]["user_prompt"])
        self.assertNotIn("CANDIDATE_BOUNDARIES", client.calls[1]["user_prompt"])
        self.assertTrue(frame_calls)
        self.assertIn("你是谁？", client.calls[0]["user_prompt"])

    def test_pipeline_reviews_each_boundary_in_a_separate_mllm_call(self) -> None:
        subtitle_payload = {
            "chapters": [
                {"start_utterance_id": "u_001", "start_time": 1.0, "end_utterance_id": "u_001", "end_time": 2.0, "title": "一", "summary": "一", "reason": "一"},
                {"start_utterance_id": "u_002", "start_time": 8.0, "end_utterance_id": "u_002", "end_time": 9.0, "title": "二", "summary": "二", "reason": "二"},
                {"start_utterance_id": "u_003", "start_time": 15.0, "end_utterance_id": "u_003", "end_time": 16.0, "title": "三", "summary": "三", "reason": "三"},
            ]
        }
        client = FakeSubtitleSceneClient(
            subtitle_payload,
            {"boundary_reviews": [{"boundary_id": "br_001", "boundary_time": 5.0, "reason": "第一处变化。"}]},
            {"boundary_reviews": [{"boundary_id": "br_002", "boundary_time": 12.0, "reason": "第二处变化。"}]},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            transcription_path = root / "video.transcription.json"
            scene_path = root / "scene_detection.json"
            video_path = root / "video.mp4"
            video_path.write_bytes(b"video")
            transcription_path.write_text(
                json.dumps(
                    {
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 0,
                                    "raw_result": {
                                        "transcripts": [
                                            {
                                                "sentences": [
                                                    {"begin_time": 1000, "end_time": 2000, "text": "第一段。"},
                                                    {"begin_time": 8000, "end_time": 9000, "text": "第二段。"},
                                                    {"begin_time": 15000, "end_time": 16000, "text": "第三段。"},
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            scene_path.write_text(
                json.dumps({"scenes": [{"scene_id": "s1", "start_time": 0.0, "end_time": 20.0}]}),
                encoding="utf-8",
            )

            def fake_extract_frames(**kwargs):
                output_dir = Path(kwargs["output_dir"])
                output_dir.mkdir(parents=True, exist_ok=True)
                for index, _timestamp in enumerate(kwargs["timestamps_seconds"], start=1):
                    (output_dir / f"frame_{index:03d}.png").write_bytes(b"png")
                return {"backend": "fake", "frame_count": len(kwargs["timestamps_seconds"])}

            StoryChapterSubtitleSceneAlignedPipeline(llm_client=client, extract_frames=fake_extract_frames).run(
                video_id="demo_three",
                video_path=video_path,
                video_metadata={"duration_seconds": 20.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=root / "output",
            )

        self.assertEqual(len(client.calls), 3)
        self.assertIn("BOUNDARY_ID: br_001", client.calls[1]["user_prompt"])
        self.assertNotIn("BOUNDARY_ID: br_002", client.calls[1]["user_prompt"])
        self.assertIn("BOUNDARY_ID: br_002", client.calls[2]["user_prompt"])

    def test_pipeline_uses_raw_subtitle_ranges_for_boundary_tasks(self) -> None:
        subtitle_payload = {
            "chapters": [
                {
                    "start_utterance_id": "u_001",
                    "start_time": 0.5,
                    "end_utterance_id": "u_001",
                    "end_time": 4.8,
                    "title": "前一章",
                    "summary": "前一章内容。",
                    "reason": "前一章原因。",
                },
                {
                    "start_utterance_id": "u_002",
                    "start_time": 4.9,
                    "end_utterance_id": "u_002",
                    "end_time": 7.0,
                    "title": "后一章",
                    "summary": "后一章内容。",
                    "reason": "后一章原因。",
                },
            ]
        }
        boundary_payload = {
            "boundary_reviews": [
                {
                    "boundary_id": "br_001",
                    "boundary_time": 5.0,
                    "reason": "5 秒这一帧是两个字幕语义章节中间的粗分界点。",
                }
            ]
        }
        client = FakeSubtitleSceneClient(subtitle_payload, boundary_payload)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            transcription_path = root / "video.transcription.json"
            scene_path = root / "scene_detection.json"
            video_path = root / "video.mp4"
            video_path.write_bytes(b"video")
            transcription_path.write_text(
                json.dumps(
                    {
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 0,
                                    "raw_result": {
                                        "transcripts": [
                                            {
                                                "sentences": [
                                                    {"begin_time": 500, "end_time": 4800, "text": "前一章。"},
                                                    {"begin_time": 4900, "end_time": 7000, "text": "后一章。"},
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            scene_path.write_text(
                json.dumps(
                    {
                        "scenes": [
                            {"scene_id": "s1", "start_time": 0.0, "end_time": 5.0},
                            {"scene_id": "s2", "start_time": 4.0, "end_time": 8.0},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def fake_extract_frames(**kwargs):
                output_dir = Path(kwargs["output_dir"])
                output_dir.mkdir(parents=True, exist_ok=True)
                for index, _timestamp in enumerate(kwargs["timestamps_seconds"], start=1):
                    (output_dir / f"frame_{index:03d}.png").write_bytes(b"png")
                return {"backend": "fake", "frame_count": len(kwargs["timestamps_seconds"])}

            output_path = StoryChapterSubtitleSceneAlignedPipeline(llm_client=client, extract_frames=fake_extract_frames).run(
                video_id="demo_overlap",
                video_path=video_path,
                video_metadata={"duration_seconds": 8.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=root / "output",
            )
            output = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(
            [(chapter["start_time"], chapter["end_time"]) for chapter in output["story_chapters"]],
            [(0.0, 5.0), (5.0, 8.0)],
        )
        self.assertEqual(output["boundary_reviews"][0]["boundary_time"], 5.0)


if __name__ == "__main__":
    unittest.main()

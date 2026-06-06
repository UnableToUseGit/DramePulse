from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter.baseline_text import Utterance
from pipelines.story_chapter.subtitle_scene_aligned import (
    StoryChapterSubtitleSceneAlignedPipeline,
    align_draft_chapters_to_scene_boundaries,
    build_draft_chapter_user_prompt,
    parse_draft_chapters,
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

    def test_pipeline_reviews_visual_gaps_with_mllm_and_inserts_standalone_chapters(self) -> None:
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
        gap_payload = {
            "gap_reviews": [
                {
                    "gap_id": "gap_001",
                    "decision": "merge_next",
                    "title": None,
                    "summary": None,
                    "reason": "片头建立下一章发生地点，应并入下一章。",
                },
                {
                    "gap_id": "gap_002",
                    "decision": "standalone",
                    "title": "骑车返乡",
                    "summary": "两人骑摩托踏上回家路。",
                    "reason": "gap 内画面是完整赶路行动，不只是前后章节转场。",
                },
                {
                    "gap_id": "gap_003",
                    "decision": "merge_previous",
                    "title": None,
                    "summary": None,
                    "reason": "片尾是上一章冲突结束后的收尾镜头。",
                }
            ]
        }
        client = FakeSubtitleSceneClient(subtitle_payload, gap_payload)
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
            [(0.0, 4.0, "开场冲突"), (4.0, 6.0, "骑车返乡"), (6.0, 12.0, "冲突收束")],
        )
        self.assertEqual(
            [(gap["start_time"], gap["end_time"], gap["previous_chapter_id"], gap["next_chapter_id"]) for gap in output["visual_gaps"]],
            [(0.0, 2.0, None, "ch_demo_ep01_001"), (4.0, 6.0, "ch_demo_ep01_001", "ch_demo_ep01_002"), (8.0, 12.0, "ch_demo_ep01_002", None)],
        )
        self.assertEqual([review["decision"] for review in output["gap_reviews"]], ["merge_next", "standalone", "merge_previous"])
        self.assertEqual(output["gap_reviews"][1]["reason"], "gap 内画面是完整赶路行动，不只是前后章节转场。")
        self.assertEqual(output["subtitle_chapters"][0]["reason"], "第一句台词建立冲突。")
        self.assertEqual(len(client.calls), 2)
        self.assertIn("PREVIOUS_CHAPTER", client.calls[1]["user_prompt"])
        self.assertIn("NEXT_CHAPTER", client.calls[1]["user_prompt"])
        self.assertTrue(frame_calls)
        self.assertIn("你是谁？", client.calls[0]["user_prompt"])

    def test_pipeline_clamps_overlapping_aligned_subtitle_chapters(self) -> None:
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
        client = FakeSubtitleSceneClient(subtitle_payload)
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

            output_path = StoryChapterSubtitleSceneAlignedPipeline(llm_client=client).run(
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
        self.assertIn("Resolved aligned subtitle chapter overlap", output["warnings"][0])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter.baseline_text import (
    StoryChapterPipeline,
    Utterance,
    build_system_prompt,
    build_user_prompt,
    load_utterances_from_transcription,
    parse_chapter_drafts,
    snap_chapter_to_scenes,
)


class FakeTextLlmClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.prompts.append(user_prompt)
        return self.payload


class StoryChapterGenerationTest(unittest.TestCase):
    def test_story_chapter_text_baseline_imports_from_new_package(self) -> None:
        from pipelines.story_chapter.baseline_text import StoryChapterPipeline

        self.assertIsNotNone(StoryChapterPipeline)

    def test_build_system_prompt_sets_role_and_json_boundary(self) -> None:
        prompt = build_system_prompt()

        self.assertIn("story chapter", prompt.lower())
        self.assertIn("timeline navigation", prompt.lower())
        self.assertIn("JSON", prompt)

    def test_build_user_prompt_uses_structured_sections_and_output_contract(self) -> None:
        prompt = build_user_prompt(
            "demo_ep01",
            12.5,
            [
                Utterance(
                    utterance_id="u_001",
                    start_time=1.0,
                    end_time=2.5,
                    speaker_id="1",
                    text="你卖的是假的。",
                )
            ],
        )

        self.assertIn("## TASK", prompt)
        self.assertIn("## INPUT", prompt)
        self.assertIn("## RULES", prompt)
        self.assertIn("## OUTPUT", prompt)
        self.assertIn("VIDEO_ID: demo_ep01", prompt)
        self.assertIn("VIDEO_DURATION_SECONDS: 12.500", prompt)
        self.assertIn("UTTERANCES:", prompt)
        self.assertIn("[1.000-2.500]", prompt)
        self.assertIn('"chapters"', prompt)
        self.assertIn("Do not output interaction triggers", prompt)
        self.assertIn("cover the full video timeline from 0.0 to VIDEO_DURATION_SECONDS", prompt)
        self.assertIn("Do not leave gaps", prompt)
        self.assertIn("left-closed and right-open", prompt)
        self.assertIn("belongs to the next chapter", prompt)
        self.assertIn("not a story-analysis category", prompt)
        self.assertIn("Avoid abstract structural titles", prompt)
        self.assertIn("Prefer concrete plot labels", prompt)

    def test_load_utterances_from_aliyun_transcription_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "video.transcription.json"
            path.write_text(
                json.dumps(
                    {
                        "provider": "aliyun",
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 10.0,
                                    "raw_result": {
                                        "transcripts": [
                                            {
                                                "sentences": [
                                                    {
                                                        "sentence_id": 7,
                                                        "begin_time": 1000,
                                                        "end_time": 2500,
                                                        "speaker_id": 2,
                                                        "text": "你卖的是假的。",
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            utterances = load_utterances_from_transcription(path)

        self.assertEqual(len(utterances), 1)
        self.assertEqual(utterances[0].utterance_id, "u_001")
        self.assertEqual(utterances[0].start_time, 11.0)
        self.assertEqual(utterances[0].end_time, 12.5)
        self.assertEqual(utterances[0].speaker_id, "2")
        self.assertEqual(utterances[0].text, "你卖的是假的。")

    def test_parse_chapter_drafts_accepts_valid_llm_chapters(self) -> None:
        drafts, warnings = parse_chapter_drafts(
            {
                "chapters": [
                    {
                        "start_time": 1.2,
                        "end_time": 8.7,
                        "title": "女主反击",
                        "summary": "女主指出关键证据，局势开始反转。",
                        "importance": 0.83,
                    }
                ]
            }
        )

        self.assertEqual(warnings, [])
        self.assertEqual(
            drafts,
            [
                {
                    "start_time": 1.2,
                    "end_time": 8.7,
                    "title": "女主反击",
                    "summary": "女主指出关键证据，局势开始反转。",
                    "importance": 0.83,
                    "source_rank": 1,
                }
            ],
        )

    def test_parse_chapter_drafts_drops_invalid_chapters(self) -> None:
        drafts, warnings = parse_chapter_drafts(
            {
                "chapters": [
                    {"start_time": 8, "end_time": 4, "title": "倒序", "summary": "时间非法", "importance": 0.5},
                    {"start_time": 1, "end_time": 2, "title": "", "summary": "标题为空", "importance": 0.5},
                    {"start_time": 1, "end_time": 2, "title": "摘要为空", "summary": "", "importance": 0.5},
                    {"start_time": 1, "end_time": 2, "title": "分数非法", "summary": "超出范围", "importance": 1.5},
                ]
            }
        )

        self.assertEqual(drafts, [])
        self.assertEqual(len(warnings), 4)

    def test_snap_chapter_to_scenes_uses_containing_scene_boundaries(self) -> None:
        scenes = [
            {"scene_id": "s_001", "start_time": 0.0, "end_time": 3.0},
            {"scene_id": "s_002", "start_time": 3.0, "end_time": 6.0},
            {"scene_id": "s_003", "start_time": 6.0, "end_time": 10.0},
        ]

        chapter = snap_chapter_to_scenes(
            {
                "start_time": 1.2,
                "end_time": 8.7,
                "title": "女主反击",
                "summary": "女主指出关键证据，局势开始反转。",
                "importance": 0.83,
                "source_rank": 1,
            },
            scenes,
        )

        self.assertIsNotNone(chapter)
        self.assertEqual(chapter["start_time"], 0.0)
        self.assertEqual(chapter["end_time"], 10.0)

    def test_snap_chapter_to_scenes_uses_nearest_boundary_outside_scene_ranges(self) -> None:
        scenes = [
            {"scene_id": "s_001", "start_time": 5.0, "end_time": 8.0},
            {"scene_id": "s_002", "start_time": 8.0, "end_time": 12.0},
        ]

        chapter = snap_chapter_to_scenes(
            {
                "start_time": 3.0,
                "end_time": 14.0,
                "title": "前后越界",
                "summary": "LLM 时间落在镜头范围外。",
                "importance": 0.5,
                "source_rank": 1,
            },
            scenes,
        )

        self.assertIsNotNone(chapter)
        self.assertEqual(chapter["start_time"], 5.0)
        self.assertEqual(chapter["end_time"], 12.0)

    def test_pipeline_writes_story_chapters_with_navigation_fields_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            transcription_path = tmp_path / "video.transcription.json"
            scene_path = tmp_path / "scene_detection.json"
            output_root = tmp_path / "output"
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
                                                    {"begin_time": 1000, "end_time": 2000, "speaker_id": 0, "text": "你卖的是假的。"},
                                                    {"begin_time": 2500, "end_time": 4000, "speaker_id": 1, "text": "你有证据吗？"},
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
                        "scenes": [
                            {"scene_id": "s_001", "start_time": 0.0, "end_time": 3.0},
                            {"scene_id": "s_002", "start_time": 3.0, "end_time": 6.0},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_client = FakeTextLlmClient(
                {
                    "chapters": [
                        {
                            "start_time": 1.2,
                            "end_time": 4.2,
                            "title": "真假争议",
                            "summary": "双方围绕瓷器真假发生争执。",
                            "importance": 0.74,
                        }
                    ]
                }
            )

            pipeline = StoryChapterPipeline(llm_client=fake_client)
            output_path = pipeline.run(
                video_id="demo_ep01",
                video_metadata={"duration_seconds": 8.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=output_root,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["video_id"], "demo_ep01")
        self.assertIn("[1.000-2.000]", fake_client.prompts[0])
        self.assertIn("VIDEO_DURATION_SECONDS: 8.000", fake_client.prompts[0])
        self.assertEqual(payload["video_metadata"], {"duration_seconds": 8.0})
        self.assertEqual(payload["story_chapters"][0]["chapter_id"], "ch_demo_ep01_001")
        self.assertEqual(payload["story_chapters"][0]["start_time"], 1.2)
        self.assertEqual(payload["story_chapters"][0]["end_time"], 4.2)
        self.assertEqual(
            set(payload["story_chapters"][0].keys()),
            {"chapter_id", "video_id", "start_time", "end_time", "title", "summary", "importance"},
        )

    def test_pipeline_keeps_raw_times_without_scene_snapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            transcription_path = tmp_path / "video.transcription.json"
            scene_path = tmp_path / "scene_detection.json"
            output_root = tmp_path / "output"
            transcription_path.write_text(
                json.dumps(
                    {
                        "raw_response": {
                            "chunks": [
                                {
                                    "offset_seconds": 0.0,
                                    "raw_result": {
                                        "transcripts": [
                                            {"sentences": [{"begin_time": 1000, "end_time": 2000, "text": "开场。"}]}
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
            scene_path.write_text(json.dumps({"scenes": []}), encoding="utf-8")
            fake_client = FakeTextLlmClient(
                {
                    "chapters": [
                        {
                            "start_time": 1.2,
                            "end_time": 4.2,
                            "title": "开场",
                            "summary": "故事开场。",
                            "importance": 0.5,
                        }
                    ]
                }
            )

            output_path = StoryChapterPipeline(llm_client=fake_client).run(
                video_id="demo_ep01",
                video_metadata={"duration_seconds": 5.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=output_root,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["story_chapters"][0]["start_time"], 1.2)
        self.assertEqual(payload["story_chapters"][0]["end_time"], 4.2)
        self.assertEqual(payload["warnings"], [])


if __name__ == "__main__":
    unittest.main()

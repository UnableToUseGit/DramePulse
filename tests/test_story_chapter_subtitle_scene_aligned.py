from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter.baseline_text import Utterance
from pipelines.story_chapter.subtitle_scene_aligned import (
    StoryChapterSubtitleSceneAlignedPipeline,
    align_draft_chapters_to_scene_boundaries,
    parse_draft_chapters,
)


class FakeSubtitleSceneClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, **kwargs})
        return self.payload


class StoryChapterSubtitleSceneAlignedTest(unittest.TestCase):
    def test_align_draft_chapters_uses_scene_end_containing_subtitle_end_time(self) -> None:
        drafts, warnings = parse_draft_chapters(
            {
                "chapters": [
                    {"end_time": 84.0, "title": "结清工钱", "summary": "讨薪事件完成。"},
                    {"end_time": 136.0, "title": "汇款报平安", "summary": "汇款后接到电话。"},
                    {"end_time": 301.133, "title": "返乡计划", "summary": "开始计划返乡。"},
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
                {"scene_id": "s4", "start_time": 85.8, "end_time": 136.833},
                {"scene_id": "s5", "start_time": 136.833, "end_time": 249.1},
                {"scene_id": "s6", "start_time": 249.1, "end_time": 301.133},
            ],
            drafts=drafts,
            max_alignment_window_seconds=8.0,
            min_chapter_seconds=12.0,
        )

        self.assertEqual(warnings, [])
        self.assertEqual(align_warnings, [])
        self.assertEqual(
            [(chapter["start_time"], chapter["end_time"]) for chapter in chapters],
            [(0.0, 85.8), (85.8, 136.833), (136.833, 301.133)],
        )
        self.assertEqual(chapters[0]["title"], "结清工钱")
        self.assertEqual(chapters[1]["alignment"]["subtitle_end_time"], 136.0)

    def test_pipeline_writes_scene_aligned_story_chapters(self) -> None:
        payload = {
            "chapters": [
                {"end_utterance_id": "u_001", "end_time": 1.2, "title": "开场冲突", "summary": "众人发生争执。"},
                {"end_utterance_id": "u_002", "end_time": 12.0, "title": "冲突收束", "summary": "冲突暂时结束。"},
            ]
        }
        client = FakeSubtitleSceneClient(payload)
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
                                                    {"begin_time": 500, "end_time": 1200, "text": "你是谁？"},
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
                            {"scene_id": "s1", "start_time": 0.0, "end_time": 6.0},
                            {"scene_id": "s2", "start_time": 6.0, "end_time": 12.0},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            output_path = StoryChapterSubtitleSceneAlignedPipeline(llm_client=client, min_chapter_seconds=3.0).run(
                video_id="demo_ep01",
                video_path=video_path,
                video_metadata={"duration_seconds": 12.0},
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=root / "output",
            )
            output = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(output["generation_mode"], "subtitle_scene_aligned")
        self.assertEqual(output["story_chapters"][0]["end_time"], 6.0)
        self.assertEqual(output["story_chapters"][-1]["end_time"], 12.0)
        self.assertIn("end_time", output["draft_chapters"][0])
        self.assertIn("你是谁？", client.calls[0]["user_prompt"])


if __name__ == "__main__":
    unittest.main()

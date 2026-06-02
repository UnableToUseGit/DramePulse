from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.highlight_candidate_generation import (
    HighlightCandidatePipeline,
    map_cue_to_scene,
    load_scenes,
    load_utterances_from_transcription,
)


class FakeTextLlmClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def generate_json_multimodal(self, *, system_prompt: str, user_prompt: str, **kwargs):
        self.prompts.append(user_prompt)
        return self.payload


class HighlightCandidateGenerationTest(unittest.TestCase):
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

    def test_map_cue_to_scene_returns_target_and_context_scenes(self) -> None:
        scenes = [
            {"scene_id": "s_001", "start_time": 0.0, "end_time": 5.0},
            {"scene_id": "s_002", "start_time": 5.0, "end_time": 10.0},
            {"scene_id": "s_003", "start_time": 10.0, "end_time": 15.0},
            {"scene_id": "s_004", "start_time": 15.0, "end_time": 20.0},
        ]

        mapped = map_cue_to_scene(
            {"cue_id": "cue_001", "cue_time": 11.0},
            scenes,
            context_size=1,
        )

        self.assertEqual(mapped["target_scene"]["scene_id"], "s_003")
        self.assertEqual(mapped["context_scene_ids"], ["s_002", "s_003", "s_004"])
        self.assertEqual(mapped["context_start_time"], 5.0)
        self.assertEqual(mapped["context_end_time"], 20.0)

    def test_pipeline_generates_cues_and_scene_cues(self) -> None:
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
                                                    {"sentence_id": 1, "begin_time": 1000, "end_time": 2000, "speaker_id": 0, "text": "你卖的是假的。"},
                                                    {"sentence_id": 2, "begin_time": 2500, "end_time": 4000, "speaker_id": 1, "text": "你有证据吗？"},
                                                    {"sentence_id": 3, "begin_time": 4200, "end_time": 7000, "speaker_id": 0, "text": "根本没有汉朝的青花瓷。"},
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
                            {"scene_id": "s_003", "start_time": 6.0, "end_time": 9.0},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_client = FakeTextLlmClient(
                {
                    "cues": [
                        {
                            "utterance_id": "u_003",
                            "highlight_type": "identity_reveal",
                            "summary": "男主指出瓷器造假。",
                            "reason": "这句台词揭穿对方造假，可能对应局势反转镜头。",
                            "confidence": 0.82,
                        }
                    ]
                }
            )

            pipeline = HighlightCandidatePipeline(llm_client=fake_client, context_size=1)
            output_path = pipeline.run(
                video_id="demo_ep01",
                transcription_path=transcription_path,
                scene_detection_path=scene_path,
                output_root=output_root,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["video_id"], "demo_ep01")
        self.assertIn("[1.000-2.000]", fake_client.prompts[0])
        self.assertEqual(payload["candidate_cues"][0]["cue_id"], "cue_001")
        self.assertEqual(payload["candidate_cues"][0]["utterance_id"], "u_003")
        self.assertEqual(payload["candidate_cues"][0]["cue_time"], 5.6)
        self.assertEqual(payload["candidate_scene_cues"][0]["target_scene"]["scene_id"], "s_002")
        self.assertEqual(payload["candidate_scene_cues"][0]["context_scene_ids"], ["s_001", "s_002", "s_003"])
        self.assertIn("根本没有汉朝的青花瓷", payload["candidate_scene_cues"][0]["context_subtitles"])


if __name__ == "__main__":
    unittest.main()

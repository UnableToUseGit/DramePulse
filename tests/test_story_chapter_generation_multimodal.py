from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.story_chapter_generation import Utterance
from pipelines.story_chapter_generation_multimodal import (
    StoryChapterMultimodalPipeline,
    build_frame_timestamps,
    build_multimodal_user_prompt,
)


class FakeMultimodalClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
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
        return self.payload


class StoryChapterGenerationMultimodalTest(unittest.TestCase):
    def test_build_frame_timestamps_uses_one_frame_per_second(self) -> None:
        self.assertEqual(build_frame_timestamps(3.2), [0.0, 1.0, 2.0, 3.0])

    def test_build_frame_timestamps_supports_interval(self) -> None:
        self.assertEqual(build_frame_timestamps(6.2, frame_interval_seconds=2.0), [0.0, 2.0, 4.0, 6.0])

    def test_build_frame_timestamps_uniformly_downsamples_when_over_max_frames(self) -> None:
        self.assertEqual(
            build_frame_timestamps(9.0, frame_interval_seconds=1.0, max_frames=4),
            [0.0, 3.0, 6.0, 9.0],
        )

    def test_build_frame_timestamps_includes_zero_for_short_video(self) -> None:
        self.assertEqual(build_frame_timestamps(0.4), [0.0])

    def test_build_multimodal_user_prompt_mentions_frames_and_boundary_rules(self) -> None:
        prompt = build_multimodal_user_prompt(
            video_id="demo_ep01",
            video_duration_seconds=12.5,
            utterances=[
                Utterance(
                    utterance_id="u_001",
                    start_time=1.0,
                    end_time=2.5,
                    speaker_id="1",
                    text="你卖的是假的。",
                )
            ],
            frame_timestamps_seconds=[0.0, 1.0, 2.0],
        )

        self.assertIn("## TASK", prompt)
        self.assertIn("VIDEO_DURATION_SECONDS: 12.500", prompt)
        self.assertIn("FRAME_TIMESTAMPS_SECONDS: 0.000, 1.000, 2.000", prompt)
        self.assertIn("Use video frames", prompt)
        self.assertIn("Internal chapter boundaries must be selected from FRAME_TIMESTAMPS_SECONDS", prompt)
        self.assertIn("The final chapter end_time must be VIDEO_DURATION_SECONDS", prompt)
        self.assertIn("not a story-analysis category", prompt)
        self.assertIn("[1.000-2.500]", prompt)

    def test_pipeline_extracts_frames_and_passes_images_to_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            transcription_path = tmp_path / "video.transcription.json"
            output_root = tmp_path / "output"
            video_path.write_bytes(b"fake")
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
            frame_dir = tmp_path / "frames"

            frame_calls: list[dict[str, object]] = []

            def fake_extract_frames(
                *,
                video_path: Path,
                output_dir: Path,
                timestamps_seconds: list[float],
                max_height: int,
            ):
                frame_calls.append(
                    {
                        "video_path": video_path,
                        "output_dir": output_dir,
                        "timestamps_seconds": timestamps_seconds,
                        "max_height": max_height,
                    }
                )
                output_dir.mkdir(parents=True, exist_ok=True)
                for timestamp in timestamps_seconds:
                    (output_dir / f"t_{int(timestamp):03d}.png").write_bytes(b"png")
                return {"backend": "fake", "frame_count": len(timestamps_seconds)}

            fake_client = FakeMultimodalClient(
                {
                    "chapters": [
                        {
                            "start_time": 0.0,
                            "end_time": 2.0,
                            "title": "故事开场",
                            "summary": "故事开始。",
                            "importance": 0.5,
                        }
                    ]
                }
            )
            pipeline = StoryChapterMultimodalPipeline(
                llm_client=fake_client,
                extract_frames=fake_extract_frames,
                frame_work_dir=frame_dir,
                frame_interval_seconds=1.0,
                max_frames=2,
            )

            output_path = pipeline.run(
                video_id="demo_ep01",
                video_path=video_path,
                video_metadata={"duration_seconds": 2.3},
                transcription_path=transcription_path,
                output_root=output_root,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(fake_client.calls[0]["frame_timestamps_seconds"], [0.0, 2.0])
        self.assertEqual(frame_calls[0]["max_height"], 512)
        self.assertEqual(len(fake_client.calls[0]["image_paths"]), 2)
        self.assertEqual(payload["frame_timestamps_seconds"], [0.0, 2.0])
        self.assertEqual(payload["frame_extraction"]["frame_count"], 2)
        self.assertEqual(payload["story_chapters"][0]["title"], "故事开场")


if __name__ == "__main__":
    unittest.main()

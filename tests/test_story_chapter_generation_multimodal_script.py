from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.run_story_chapter_generation_multimodal import build_parser, main


class StoryChapterGenerationMultimodalScriptTest(unittest.TestCase):
    def test_main_passes_video_inputs_to_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            transcription_path = tmp_path / "video.transcription.json"
            scene_path = tmp_path / "scene_detection.json"
            output_root = tmp_path / "output"
            video_path.write_bytes(b"video")
            transcription_path.write_text("{}", encoding="utf-8")
            scene_path.write_text('{"scenes":[{"start_time":0,"end_time":12.5}]}', encoding="utf-8")

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(
                    self,
                    *,
                    video_id: str,
                    video_path: Path,
                    video_metadata: dict[str, object],
                    transcription_path: Path,
                    output_root: Path,
                ) -> Path:
                    self.calls.append(
                        {
                            "video_id": video_id,
                            "video_path": video_path,
                            "video_metadata": video_metadata,
                            "transcription_path": transcription_path,
                            "output_root": output_root,
                        }
                    )
                    output_path = output_root / video_id / "story_chapters.json"
                    output_path.parent.mkdir(parents=True)
                    output_path.write_text("{}", encoding="utf-8")
                    return output_path

            pipeline = FakePipeline()
            result = main(
                [
                    "demo_ep01",
                    "--video",
                    str(video_path),
                    "--transcription",
                    str(transcription_path),
                    "--scene-detection",
                    str(scene_path),
                    "--output-root",
                    str(output_root),
                    "--frame-interval-seconds",
                    "2",
                    "--max-frames",
                    "50",
                ],
                pipeline=pipeline,
            )

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls[0]["video_id"], "demo_ep01")
        self.assertEqual(pipeline.calls[0]["video_path"], video_path)
        self.assertEqual(pipeline.calls[0]["video_metadata"], {"duration_seconds": 12.5})
        self.assertEqual(pipeline.calls[0]["transcription_path"], transcription_path)

    def test_parser_accepts_frame_sampling_options(self) -> None:
        args = build_parser().parse_args(
            [
                "demo_ep01",
                "--video",
                "video.mp4",
                "--transcription",
                "video.transcription.json",
                "--scene-detection",
                "scene_detection.json",
                "--frame-interval-seconds",
                "2",
                "--max-frames",
                "50",
            ]
        )

        self.assertEqual(args.frame_interval_seconds, 2.0)
        self.assertEqual(args.max_frames, 50)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.run_story_chapter_generation_multimodal_batch import build_parser, discover_multimodal_inputs, main


REPO_ROOT = Path(__file__).resolve().parents[1]


class StoryChapterGenerationMultimodalBatchScriptTest(unittest.TestCase):
    def test_new_story_chapter_mllm_batch_algorithm_script_runs_when_executed_directly(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/algorithm/story_chapter/run_mllm_batch.py", "--help"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Batch run multimodal story chapter generation", result.stdout)

    def test_discover_multimodal_inputs_requires_video_transcription_and_scene_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "video.transcription.json").write_text("{}", encoding="utf-8")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps({"video_id": "scene_video_id", "scenes": [{"start_time": 0, "end_time": 3}]}),
                encoding="utf-8",
            )

            inputs = discover_multimodal_inputs(root)

        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].video_id, "scene_video_id")
        self.assertEqual(inputs[0].video_path, episode_dir / "video.mp4")

    def test_main_runs_pipeline_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "dataset"
            output_root = Path(tmpdir) / "output"
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            video_path = episode_dir / "video.mp4"
            transcription_path = episode_dir / "video.transcription.json"
            scene_path = episode_dir / "scene_detection.json"
            video_path.write_bytes(b"video")
            transcription_path.write_text("{}", encoding="utf-8")
            scene_path.write_text(
                json.dumps({"video_id": "demo_series_ep01", "scenes": [{"start_time": 0, "end_time": 9.25}]}),
                encoding="utf-8",
            )

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
                    "--dataset-root",
                    str(root),
                    "--output-root",
                    str(output_root),
                ],
                pipeline=pipeline,
            )
            summary = json.loads(
                (output_root / "story_chapter_multimodal_batch_summary.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls[0]["video_id"], "demo_series_ep01")
        self.assertEqual(pipeline.calls[0]["video_path"], video_path)
        self.assertEqual(pipeline.calls[0]["video_metadata"], {"duration_seconds": 9.25})
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["failed"], 0)

    def test_main_skips_existing_outputs_when_only_missing_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "dataset"
            output_root = Path(tmpdir) / "output"
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "video.transcription.json").write_text("{}", encoding="utf-8")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps({"video_id": "demo_series_ep01", "scenes": [{"start_time": 0, "end_time": 9.25}]}),
                encoding="utf-8",
            )
            existing_output = output_root / "demo_series_ep01" / "story_chapters.json"
            existing_output.parent.mkdir(parents=True)
            existing_output.write_text("{}", encoding="utf-8")

            class FakePipeline:
                calls: list[dict[str, object]] = []

                def run(self, **kwargs) -> Path:
                    self.calls.append(kwargs)
                    return existing_output

            pipeline = FakePipeline()
            result = main(
                [
                    "--dataset-root",
                    str(root),
                    "--output-root",
                    str(output_root),
                    "--only-missing",
                ],
                pipeline=pipeline,
            )
            summary = json.loads(
                (output_root / "story_chapter_multimodal_batch_summary.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls, [])
        self.assertEqual(summary["skipped"], 1)

    def test_parser_accepts_frame_sampling_options(self) -> None:
        args = build_parser().parse_args(
            [
                "--dataset-root",
                "dataset",
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

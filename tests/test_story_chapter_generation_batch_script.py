from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_story_chapter_generation_batch import discover_story_chapter_inputs, main


class StoryChapterGenerationBatchScriptTest(unittest.TestCase):
    def test_discover_story_chapter_inputs_finds_dataset_episodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.transcription.json").write_text("{}", encoding="utf-8")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps({"video_id": "scene_video_id", "scenes": []}),
                encoding="utf-8",
            )

            inputs = discover_story_chapter_inputs(root)

        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].video_id, "scene_video_id")
        self.assertEqual(inputs[0].series_slug, "demo_series")
        self.assertEqual(inputs[0].episode_slug, "ep01")

    def test_discover_story_chapter_inputs_falls_back_to_series_episode_video_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "demo_series" / "ep02"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.transcription.json").write_text("{}", encoding="utf-8")
            (episode_dir / "scene_detection.json").write_text("{bad json", encoding="utf-8")

            inputs = discover_story_chapter_inputs(root)

        self.assertEqual(inputs[0].video_id, "demo_series_ep02")

    def test_main_runs_pipeline_for_discovered_inputs_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "dataset"
            output_root = Path(tmpdir) / "output"
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            transcription_path = episode_dir / "video.transcription.json"
            scene_path = episode_dir / "scene_detection.json"
            transcription_path.write_text("{}", encoding="utf-8")
            scene_path.write_text(json.dumps({"video_id": "demo_series_ep01"}), encoding="utf-8")

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(
                    self,
                    *,
                    video_id: str,
                    transcription_path: Path,
                    scene_detection_path: Path,
                    output_root: Path,
                ) -> Path:
                    self.calls.append(
                        {
                            "video_id": video_id,
                            "transcription_path": transcription_path,
                            "scene_detection_path": scene_detection_path,
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

            summary = json.loads((output_root / "story_chapter_generation_batch_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls[0]["video_id"], "demo_series_ep01")
        self.assertEqual(pipeline.calls[0]["transcription_path"], transcription_path)
        self.assertEqual(pipeline.calls[0]["scene_detection_path"], scene_path)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["failed"], 0)

    def test_main_skips_existing_outputs_when_only_missing_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "dataset"
            output_root = Path(tmpdir) / "output"
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.transcription.json").write_text("{}", encoding="utf-8")
            (episode_dir / "scene_detection.json").write_text(json.dumps({"video_id": "demo_series_ep01"}), encoding="utf-8")
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
            summary = json.loads((output_root / "story_chapter_generation_batch_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls, [])
        self.assertEqual(summary["skipped"], 1)


if __name__ == "__main__":
    unittest.main()

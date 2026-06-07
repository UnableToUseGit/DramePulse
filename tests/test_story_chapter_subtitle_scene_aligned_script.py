from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.story_chapter.run_subtitle_scene_aligned import build_parser as build_single_parser
from scripts.story_chapter.run_subtitle_scene_aligned import main as single_main
from scripts.story_chapter.run_subtitle_scene_aligned_batch import discover_subtitle_scene_aligned_inputs
from scripts.story_chapter.run_subtitle_scene_aligned_batch import build_parser as build_batch_parser
from scripts.story_chapter.run_subtitle_scene_aligned_batch import main as batch_main


class StoryChapterSubtitleSceneAlignedScriptTest(unittest.TestCase):
    def test_single_parser_rejects_removed_alignment_tuning_options(self) -> None:
        with self.assertRaises(SystemExit):
            build_single_parser().parse_args(
                [
                    "demo_series_ep01",
                    "--video",
                    "video.mp4",
                    "--transcription",
                    "video.transcription.json",
                    "--scene-detection",
                    "scene_detection.json",
                    "--max-alignment-window-seconds",
                    "8",
                ]
            )

    def test_batch_parser_rejects_removed_alignment_tuning_options(self) -> None:
        with self.assertRaises(SystemExit):
            build_batch_parser().parse_args(
                [
                    "--dataset-root",
                    "dataset",
                    "--min-chapter-seconds",
                    "8",
                ]
            )

    def test_single_main_passes_series_id_to_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            video_path = root / "video.mp4"
            transcription_path = root / "video.transcription.json"
            scene_path = root / "scene_detection.json"
            output_root = root / "output"
            video_path.write_bytes(b"video")
            transcription_path.write_text("{}", encoding="utf-8")
            scene_path.write_text(
                json.dumps({"scenes": [{"start_time": 0.0, "end_time": 12.5}]}),
                encoding="utf-8",
            )

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(
                    self,
                    *,
                    video_id: str,
                    series_id: str | None,
                    video_path: Path,
                    video_metadata: dict[str, object],
                    transcription_path: Path,
                    scene_detection_path: Path,
                    output_root: Path,
                ) -> Path:
                    self.calls.append(
                        {
                            "video_id": video_id,
                            "series_id": series_id,
                            "video_path": video_path,
                            "video_metadata": video_metadata,
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
            result = single_main(
                [
                    "demo_series_ep01",
                    "--series-id",
                    "demo_series",
                    "--video",
                    str(video_path),
                    "--transcription",
                    str(transcription_path),
                    "--scene-detection",
                    str(scene_path),
                    "--output-root",
                    str(output_root),
                ],
                pipeline=pipeline,
            )

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls[0]["video_id"], "demo_series_ep01")
        self.assertEqual(pipeline.calls[0]["series_id"], "demo_series")
        self.assertEqual(pipeline.calls[0]["video_metadata"], {"duration_seconds": 12.5})

    def test_batch_main_passes_dataset_series_slug_to_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_root = Path(tmpdir) / "dataset"
            output_root = Path(tmpdir) / "output"
            episode_dir = dataset_root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            video_path = episode_dir / "video.mp4"
            transcription_path = episode_dir / "video.transcription.json"
            scene_path = episode_dir / "scene_detection.json"
            video_path.write_bytes(b"video")
            transcription_path.write_text("{}", encoding="utf-8")
            scene_path.write_text(
                json.dumps({"video_id": "demo_series_ep01", "scenes": [{"start_time": 0.0, "end_time": 9.25}]}),
                encoding="utf-8",
            )

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(
                    self,
                    *,
                    video_id: str,
                    series_id: str | None,
                    video_path: Path,
                    video_metadata: dict[str, object],
                    transcription_path: Path,
                    scene_detection_path: Path,
                    output_root: Path,
                ) -> Path:
                    self.calls.append(
                        {
                            "video_id": video_id,
                            "series_id": series_id,
                            "video_path": video_path,
                            "video_metadata": video_metadata,
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
            result = batch_main(
                [
                    "--dataset-root",
                    str(dataset_root),
                    "--output-root",
                    str(output_root),
                ],
                pipeline=pipeline,
            )
            summary = json.loads(
                (output_root / "story_chapter_subtitle_scene_aligned_batch_summary.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, 0)
        self.assertEqual(pipeline.calls[0]["video_id"], "demo_series_ep01")
        self.assertEqual(pipeline.calls[0]["series_id"], "demo_series")
        self.assertEqual(pipeline.calls[0]["video_path"], video_path)
        self.assertEqual(pipeline.calls[0]["video_metadata"], {"duration_seconds": 9.25})
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["failed"], 0)

    def test_batch_discovery_falls_back_when_scene_detection_video_id_is_generic_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_root = Path(tmpdir) / "dataset"
            for episode_id in ("ep04", "ep05"):
                episode_dir = dataset_root / "naniandongzhi" / episode_id
                episode_dir.mkdir(parents=True)
                (episode_dir / "video.mp4").write_bytes(b"video")
                (episode_dir / "video.transcription.json").write_text("{}", encoding="utf-8")
                (episode_dir / "scene_detection.json").write_text(
                    json.dumps({"video_id": "video", "scenes": [{"start_time": 0.0, "end_time": 9.25}]}),
                    encoding="utf-8",
                )

            inputs = discover_subtitle_scene_aligned_inputs(dataset_root)

        self.assertEqual([item.video_id for item in inputs], ["naniandongzhi_ep04", "naniandongzhi_ep05"])


if __name__ == "__main__":
    unittest.main()

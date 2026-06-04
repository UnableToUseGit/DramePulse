from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.run_story_chapter_generation import main


REPO_ROOT = Path(__file__).resolve().parents[1]


class StoryChapterGenerationScriptTest(unittest.TestCase):
    def test_new_story_chapter_text_algorithm_script_runs_when_executed_directly(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/algorithm/story_chapter/run_text.py", "--help"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("subtitle-based story chapter generation", result.stdout)

    def test_main_passes_paths_to_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            transcription_path = tmp_path / "video.transcription.json"
            scene_path = tmp_path / "scene_detection.json"
            output_root = tmp_path / "output"
            transcription_path.write_text("{}", encoding="utf-8")
            scene_path.write_text('{"scenes":[{"start_time":0,"end_time":12.5}]}', encoding="utf-8")

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(
                    self,
                    *,
                    video_id: str,
                    video_metadata: dict[str, object],
                    transcription_path: Path,
                    scene_detection_path: Path,
                    output_root: Path,
                ) -> Path:
                    self.calls.append(
                        {
                            "video_id": video_id,
                            "video_metadata": video_metadata,
                            "transcription_path": transcription_path,
                            "scene_detection_path": scene_detection_path,
                            "output_root": output_root,
                        }
                    )
                    output_root.mkdir(parents=True)
                    output_path = output_root / video_id / "story_chapters.json"
                    output_path.parent.mkdir()
                    output_path.write_text("{}", encoding="utf-8")
                    return output_path

            pipeline = FakePipeline()
            result = main(
                [
                    "demo_ep01",
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
            self.assertEqual(pipeline.calls[0]["video_id"], "demo_ep01")
            self.assertEqual(pipeline.calls[0]["video_metadata"], {"duration_seconds": 12.5})
            self.assertEqual(pipeline.calls[0]["transcription_path"], transcription_path)
            self.assertEqual(pipeline.calls[0]["scene_detection_path"], scene_path)
            self.assertEqual(pipeline.calls[0]["output_root"], output_root)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.video_preprocess.run_pipeline import run_video_preprocess


class VideoPreprocessPipelineTest(unittest.TestCase):
    def test_run_video_preprocess_orchestrates_audio_transcription_and_scene_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "demo.mp4"
            video_path.write_bytes(b"fake-video")
            output_root = tmp_path / "output"
            calls: list[str] = []

            def fake_extract_audio(*, video_path: Path, output_dir: Path) -> Path:
                calls.append("audio")
                output_dir.mkdir(parents=True)
                audio_path = output_dir / "demo.16k-mono.wav"
                audio_path.write_bytes(b"wav")
                return audio_path

            def fake_transcribe(*, video_path: Path, output_dir: Path, env_path: Path | None) -> Path:
                calls.append("transcription")
                output_dir.mkdir(parents=True)
                subtitle_path = output_dir / "demo.srt"
                subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")
                return subtitle_path

            def fake_detect_scenes(
                *,
                video_path: Path,
                video_id: str,
                output_dir: Path,
                threshold: float,
                min_scene_len: int,
                show_progress: bool,
                split_segments: bool,
            ) -> Path:
                calls.append("scene")
                self.assertEqual(video_id, "demo_ep01")
                self.assertEqual(threshold, 22.0)
                self.assertEqual(min_scene_len, 9)
                self.assertFalse(show_progress)
                self.assertFalse(split_segments)
                output_dir.mkdir(parents=True)
                scene_path = output_dir / "scene_detection.json"
                scene_path.write_text(json.dumps({"video_id": video_id, "scenes": []}), encoding="utf-8")
                return scene_path

            result = run_video_preprocess(
                video_path=video_path,
                video_id="demo_ep01",
                output_root=output_root,
                env_path=tmp_path / ".env",
                threshold=22.0,
                min_scene_len=9,
                split_segments=False,
                extract_audio=fake_extract_audio,
                transcribe=fake_transcribe,
                detect_scenes=fake_detect_scenes,
            )

            self.assertEqual(calls, ["audio", "transcription", "scene"])
            self.assertEqual(result.video_id, "demo_ep01")
            self.assertTrue(result.audio_path.is_file())
            self.assertTrue(result.subtitle_path.is_file())
            self.assertTrue(result.scene_detection_path.is_file())
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["pipeline"], "video-preprocess")
            self.assertEqual(manifest["video_id"], "demo_ep01")
            self.assertEqual(manifest["artifacts"]["audio_path"], "audio/demo.16k-mono.wav")
            self.assertEqual(manifest["artifacts"]["subtitle_path"], "transcription/demo.srt")
            self.assertEqual(manifest["artifacts"]["scene_detection_path"], "scene_detection/scene_detection.json")


if __name__ == "__main__":
    unittest.main()

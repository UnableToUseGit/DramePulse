from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import run_scene_detection


class FakeTimecode:
    def __init__(self, seconds: float, frame_num: int) -> None:
        self.seconds = seconds
        self.frame_num = frame_num

    def get_timecode(self) -> str:
        whole_seconds = int(self.seconds)
        millis = int(round((self.seconds - whole_seconds) * 1000))
        return f"00:00:{whole_seconds:02d}.{millis:03d}"

    def __sub__(self, other: "FakeTimecode") -> "FakeTimecode":
        return FakeTimecode(self.seconds - other.seconds, self.frame_num - other.frame_num)


class SceneDetectionScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.video_dir = self.tmp_path / "VideoData" / "raw" / "demo" / "ep01"
        self.video_dir.mkdir(parents=True)
        self.video_path = self.video_dir / "video.mp4"
        self.video_path.write_bytes(b"fake video")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_resolve_video_input_derives_video_id_from_path_stem(self) -> None:
        video = run_scene_detection.resolve_video_input(self.video_path)

        self.assertEqual(video.video_id, "video")
        self.assertEqual(video.title, "video")
        self.assertEqual(video.video_path, self.video_path.resolve())

    def test_resolve_video_input_uses_explicit_video_id(self) -> None:
        video = run_scene_detection.resolve_video_input(self.video_path, video_id="beipai_xunbao_biji_ep02")

        self.assertEqual(video.video_id, "beipai_xunbao_biji_ep02")
        self.assertEqual(video.title, "beipai_xunbao_biji_ep02")
        self.assertEqual(video.video_path, self.video_path.resolve())

    def test_detect_video_writes_scene_json_and_video_segments(self) -> None:
        def fake_detect(video_path: Path, threshold: float, min_scene_len: int, show_progress: bool):
            self.assertEqual(video_path, self.video_path.resolve())
            self.assertEqual(threshold, 22.0)
            self.assertEqual(min_scene_len, 15)
            self.assertFalse(show_progress)
            return [
                (FakeTimecode(0.0, 0), FakeTimecode(4.5, 135)),
                (FakeTimecode(4.5, 135), FakeTimecode(9.0, 270)),
            ]

        def fake_split(video_path: Path, scenes, output_dir: Path, video_id: str, show_progress: bool) -> list[Path]:
            self.assertEqual(video_path, self.video_path.resolve())
            self.assertEqual(len(scenes), 2)
            self.assertEqual(video_id, "demo_ep01")
            self.assertFalse(show_progress)
            output_dir.mkdir(parents=True)
            paths = [output_dir / "demo_ep01_scene_001.mp4", output_dir / "demo_ep01_scene_002.mp4"]
            for path in paths:
                path.write_bytes(b"clip")
            return paths

        output_path = run_scene_detection.detect_video(
            run_scene_detection.LocalVideo(video_id="demo_ep01", title="Demo Episode", video_path=self.video_path.resolve()),
            output_root=self.tmp_path / "output",
            threshold=22.0,
            min_scene_len=15,
            show_progress=False,
            detect_scenes=fake_detect,
            split_scenes=fake_split,
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["video_id"], "demo_ep01")
        self.assertEqual(payload["detector"]["type"], "content")
        self.assertEqual(payload["detector"]["threshold"], 22.0)
        self.assertEqual(payload["detector"]["min_scene_len"], 15)
        self.assertEqual(len(payload["scenes"]), 2)
        self.assertEqual(payload["scenes"][0]["scene_id"], "demo_ep01_scene_001")
        self.assertEqual(payload["scenes"][0]["start_time"], 0.0)
        self.assertEqual(payload["scenes"][0]["end_time"], 4.5)
        self.assertEqual(payload["scenes"][0]["duration"], 4.5)
        self.assertEqual(payload["scenes"][0]["clip_path"], "scenes/demo_ep01_scene_001.mp4")
        self.assertTrue((self.tmp_path / "output" / "demo_ep01" / "scenes" / "demo_ep01_scene_001.mp4").is_file())

    def test_detect_video_can_skip_video_segment_splitting(self) -> None:
        split_calls: list[object] = []

        def fake_detect(video_path: Path, threshold: float, min_scene_len: int, show_progress: bool):
            return [
                (FakeTimecode(0.0, 0), FakeTimecode(4.5, 135)),
                (FakeTimecode(4.5, 135), FakeTimecode(9.0, 270)),
            ]

        def fake_split(video_path: Path, scenes, output_dir: Path, video_id: str, show_progress: bool) -> list[Path]:
            split_calls.append((video_path, scenes, output_dir, video_id, show_progress))
            return []

        output_path = run_scene_detection.detect_video(
            run_scene_detection.LocalVideo(video_id="demo_ep01", title="Demo Episode", video_path=self.video_path.resolve()),
            output_root=self.tmp_path / "output",
            threshold=22.0,
            min_scene_len=15,
            show_progress=False,
            split_segments=False,
            detect_scenes=fake_detect,
            split_scenes=fake_split,
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(split_calls, [])
        self.assertEqual(payload["scene_count"], 2)
        self.assertIsNone(payload["scenes"][0]["clip_path"])
        self.assertFalse((self.tmp_path / "output" / "demo_ep01" / "scenes").exists())

    def test_detect_video_can_write_to_explicit_output_dir(self) -> None:
        def fake_detect(video_path: Path, threshold: float, min_scene_len: int, show_progress: bool):
            return [(FakeTimecode(0.0, 0), FakeTimecode(4.5, 135))]

        output_path = run_scene_detection.detect_video(
            run_scene_detection.LocalVideo(video_id="demo_ep01", title="Demo Episode", video_path=self.video_path.resolve()),
            output_root=self.tmp_path / "ignored-root",
            output_dir=self.video_dir,
            threshold=22.0,
            min_scene_len=15,
            show_progress=False,
            split_segments=False,
            detect_scenes=fake_detect,
        )

        self.assertEqual(output_path, self.video_dir / "scene_detection.json")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["video_id"], "demo_ep01")

    def test_resolve_video_input_requires_existing_file(self) -> None:
        missing_path = self.tmp_path / "missing.mp4"

        with self.assertRaisesRegex(FileNotFoundError, "Video file not found"):
            run_scene_detection.resolve_video_input(missing_path)


if __name__ == "__main__":
    unittest.main()

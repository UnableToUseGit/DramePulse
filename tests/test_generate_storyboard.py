from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from scripts.generate_storyboard import build_parser, build_storyboard_from_frames


class GenerateStoryboardTest(unittest.TestCase):
    def write_frame(self, directory: Path, index: int, color: tuple[int, int, int]) -> Path:
        path = directory / f"frame_{index:03d}.jpg"
        image = np.zeros((8, 12, 3), dtype=np.uint8)
        image[:, :] = (color[2], color[1], color[0])
        cv2.imwrite(str(path), image)
        return path

    def test_build_storyboard_from_frames_writes_sheets_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            frame_dir = root / "frames"
            output_dir = root / "storyboard"
            frame_dir.mkdir()
            frames = [
                self.write_frame(frame_dir, 0, (255, 0, 0)),
                self.write_frame(frame_dir, 1, (0, 255, 0)),
                self.write_frame(frame_dir, 2, (0, 0, 255)),
            ]

            manifest_path = build_storyboard_from_frames(
                video_id="demo_ep01",
                frame_paths=frames,
                output_dir=output_dir,
                interval_seconds=1.0,
                frame_width=16,
                frame_height=9,
                columns=2,
                rows=1,
                url_prefix="/static/storyboards/demo_ep01",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue((output_dir / "sheet_000.jpg").exists())
            self.assertTrue((output_dir / "sheet_001.jpg").exists())
            sheet_000 = cv2.imread(str(output_dir / "sheet_000.jpg"))
            sheet_001 = cv2.imread(str(output_dir / "sheet_001.jpg"))
            self.assertEqual(sheet_000.shape[:2], (9, 32))
            self.assertEqual(sheet_001.shape[:2], (9, 32))

        self.assertEqual(manifest["video_id"], "demo_ep01")
        self.assertEqual(manifest["interval_seconds"], 1.0)
        self.assertEqual(manifest["frame_width"], 16)
        self.assertEqual(manifest["frame_height"], 9)
        self.assertEqual(manifest["columns"], 2)
        self.assertEqual(manifest["rows"], 1)
        self.assertEqual(len(manifest["sheets"]), 2)
        self.assertEqual(
            manifest["sheets"][0],
            {
                "url": "/static/storyboards/demo_ep01/sheet_000.jpg",
                "start_time": 0.0,
                "frame_count": 2,
            },
        )
        self.assertEqual(manifest["sheets"][1]["url"], "/static/storyboards/demo_ep01/sheet_001.jpg")
        self.assertEqual(manifest["sheets"][1]["start_time"], 2.0)
        self.assertEqual(manifest["sheets"][1]["frame_count"], 1)

    def test_build_storyboard_from_frames_can_infer_source_aspect_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            frame_dir = root / "frames"
            output_dir = root / "storyboard"
            frame_dir.mkdir()
            frame_path = frame_dir / "frame_000.jpg"
            image = np.zeros((12, 8, 3), dtype=np.uint8)
            image[:, :] = (255, 255, 255)
            cv2.imwrite(str(frame_path), image)

            manifest_path = build_storyboard_from_frames(
                video_id="demo_ep01",
                frame_paths=[frame_path],
                output_dir=output_dir,
                interval_seconds=1.0,
                frame_width=16,
                frame_height=None,
                columns=1,
                rows=1,
                url_prefix="/static/storyboards/demo_ep01",
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sheet = cv2.imread(str(output_dir / "sheet_000.jpg"))

        self.assertEqual(manifest["frame_width"], 16)
        self.assertEqual(manifest["frame_height"], 24)
        self.assertEqual(sheet.shape[:2], (24, 16))

    def test_build_storyboard_from_frames_rejects_empty_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "at least one frame"):
                build_storyboard_from_frames(
                    video_id="demo_ep01",
                    frame_paths=[],
                    output_dir=Path(tmpdir),
                    interval_seconds=1.0,
                    frame_width=16,
                    frame_height=9,
                    columns=2,
                    rows=2,
                    url_prefix="/static/storyboards/demo_ep01",
                )

    def test_parser_accepts_storyboard_options(self) -> None:
        args = build_parser().parse_args(
            [
                "demo_ep01",
                "--video",
                "video.mp4",
                "--output-dir",
                "out",
                "--interval-seconds",
                "2",
                "--frame-width",
                "160",
                "--frame-height",
                "90",
                "--columns",
                "5",
                "--rows",
                "5",
                "--url-prefix",
                "/static/storyboards/demo_ep01",
            ]
        )

        self.assertEqual(args.video_id, "demo_ep01")
        self.assertEqual(args.video, Path("video.mp4"))
        self.assertEqual(args.output_dir, Path("out"))
        self.assertEqual(args.interval_seconds, 2.0)
        self.assertEqual(args.frame_width, 160)
        self.assertEqual(args.frame_height, 90)
        self.assertEqual(args.columns, 5)
        self.assertEqual(args.rows, 5)
        self.assertEqual(args.url_prefix, "/static/storyboards/demo_ep01")


if __name__ == "__main__":
    unittest.main()

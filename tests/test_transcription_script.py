from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.transcribe_video import main


class TranscriptionScriptTest(unittest.TestCase):
    def test_main_writes_srt_for_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "demo.mp4"
            output_path = tmp_path / "demo.srt"
            video_path.write_bytes(b"fake-video")

            class FakeRunner:
                def __init__(self) -> None:
                    self.called = False

                def __call__(self, *, video_path: Path, output_path: Path) -> Path:
                    self.called = True
                    output_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")
                    return output_path

            fake_runner = FakeRunner()
            result = main(
                [
                    str(video_path),
                    "--output",
                    str(output_path),
                ],
                runner=fake_runner,
            )

            self.assertTrue(fake_runner.called)
            self.assertEqual(result, 0)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "1\n00:00:00,000 --> 00:00:01,000\n你好\n")


if __name__ == "__main__":
    unittest.main()

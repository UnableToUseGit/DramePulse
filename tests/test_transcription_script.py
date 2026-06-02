from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.transcribe_video import main


class TranscriptionScriptTest(unittest.TestCase):
    def test_main_writes_outputs_to_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "demo.mp4"
            output_dir = tmp_path / "output"
            video_path.write_bytes(b"fake-video")

            class FakeRunner:
                def __init__(self) -> None:
                    self.called = False

                def __call__(self, *, video_path: Path, output_dir: Path, env_path: Path | None = None) -> Path:
                    self.called = True
                    output_dir.mkdir(parents=True)
                    output_path = output_dir / "demo.srt"
                    output_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")
                    return output_path

            fake_runner = FakeRunner()
            result = main(
                [
                    str(video_path),
                    "--output",
                    str(output_dir),
                ],
                runner=fake_runner,
            )

            self.assertTrue(fake_runner.called)
            self.assertEqual(result, 0)
            output_path = output_dir / "demo.srt"
            self.assertEqual(output_path.read_text(encoding="utf-8"), "1\n00:00:00,000 --> 00:00:01,000\n你好\n")

    def test_main_passes_env_file_to_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "demo.mp4"
            output_dir = tmp_path / "output"
            env_path = tmp_path / ".env"
            video_path.write_bytes(b"fake-video")
            env_path.write_text("OSS_BUCKET_NAME=demo\n", encoding="utf-8")

            class FakeRunner:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def __call__(self, *, video_path: Path, output_dir: Path, env_path: Path | None = None) -> Path:
                    self.calls.append(
                        {
                            "video_path": video_path,
                            "output_dir": output_dir,
                            "env_path": env_path,
                        }
                    )
                    output_dir.mkdir(parents=True)
                    output_path = output_dir / "demo.srt"
                    output_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")
                    return output_path

            fake_runner = FakeRunner()
            result = main(
                [
                    str(video_path),
                    "--output",
                    str(output_dir),
                    "--env-file",
                    str(env_path),
                ],
                runner=fake_runner,
            )

            self.assertEqual(result, 0)
            self.assertEqual(fake_runner.calls[0]["env_path"], env_path)
            self.assertEqual(fake_runner.calls[0]["output_dir"], output_dir)


if __name__ == "__main__":
    unittest.main()

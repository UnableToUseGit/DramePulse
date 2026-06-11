from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest

from dramepulse_cli.main import main
from dramepulse_cli.registry import PipelineCommand


class DramePulseCliTest(unittest.TestCase):
    def test_version_prints_project_version(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["--version"])

        self.assertEqual(exit_code, 0)
        self.assertIn("DramePulse 0.1.0", stdout.getvalue())

    def test_help_prints_ansi_banner_and_pipeline_commands(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["--help"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("\x1b[", output)
        self.assertIn("DramePulse", output)
        self.assertIn("pipelines list", output)
        self.assertIn("pipelines info <name>", output)
        self.assertIn("pipelines run <name>", output)
        self.assertIn("video-preprocess", output)
        self.assertIn("highlight-commerce", output)
        self.assertIn("plot-beat", output)

    def test_pipeline_list_and_info_show_registry_metadata(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            list_exit = main(["pipelines", "list"])
            info_exit = main(["pipelines", "info", "highlight-commerce"])

        output = stdout.getvalue()
        self.assertEqual(list_exit, 0)
        self.assertEqual(info_exit, 0)
        self.assertIn("highlight-commerce", output)
        self.assertIn("高光带货", output)
        self.assertIn("scripts.highlight_commerce.run_v2_pipeline", output)
        self.assertIn("dramepulse pipelines run highlight-commerce", output)

    def test_plot_beat_pipeline_is_registered(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            list_exit = main(["pipelines", "list"])
            info_exit = main(["pipelines", "info", "plot-beat"])

        output = stdout.getvalue()
        self.assertEqual(list_exit, 0)
        self.assertEqual(info_exit, 0)
        self.assertIn("plot-beat", output)
        self.assertIn("Plot Beat", output)
        self.assertIn("scripts.plot_beat.run_chapter_aligned_batch", output)
        self.assertIn("plot_beats.json", output)

    def test_video_preprocess_pipeline_is_registered(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            list_exit = main(["pipelines", "list"])
            info_exit = main(["pipelines", "info", "video-preprocess"])

        output = stdout.getvalue()
        self.assertEqual(list_exit, 0)
        self.assertEqual(info_exit, 0)
        self.assertIn("video-preprocess", output)
        self.assertIn("Video Preprocess", output)
        self.assertIn("scripts.video_preprocess.run_pipeline", output)
        self.assertIn("video_preprocess_manifest.json", output)

    def test_pipeline_run_forwards_remaining_args_to_registered_runner(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(argv: list[str]) -> int:
            calls.append(argv)
            return 7

        registry = [
            PipelineCommand(
                name="fake-pipeline",
                title="Fake Pipeline",
                summary="Used by tests.",
                module="tests.fake_pipeline",
                runner=fake_runner,
                example_args=["--input", "demo.json"],
                outputs=["demo_output.json"],
            )
        ]

        exit_code = main(
            ["pipelines", "run", "fake-pipeline", "--input", "a.json", "--force"],
            registry=registry,
        )

        self.assertEqual(exit_code, 7)
        self.assertEqual(calls, [["--input", "a.json", "--force"]])


if __name__ == "__main__":
    unittest.main()

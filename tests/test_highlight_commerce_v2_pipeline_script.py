from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from scripts.highlight_commerce.run_v2_pipeline import main


class HighlightCommerceV2PipelineScriptTest(unittest.TestCase):
    def test_main_loads_asset_runs_pipeline_and_writes_output(self) -> None:
        class FakePipeline:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def run(self, asset: dict[str, object], **kwargs: object) -> dict[str, object]:
                self.calls.append({"asset": asset, **kwargs})
                return {
                    **asset,
                    "pipeline_version": "highlight_commerce_v2",
                    "render": {
                        "provider_job_id": "task-001",
                        "render_status": "succeeded",
                        "output_video_path": str(kwargs["output_dir"] / "highlight_commerce_seedance.mp4"),  # type: ignore[operator]
                    },
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset_path = root / "asset.json"
            output_root = root / "output"
            asset_path.write_text(json.dumps({"campaign_id": "case1"}), encoding="utf-8")
            pipeline = FakePipeline()
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--asset",
                        str(asset_path),
                        "--output-root",
                        str(output_root),
                        "--no-wait",
                    ],
                    pipeline=pipeline,
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(pipeline.calls[0]["output_dir"], output_root / "case1")
        self.assertEqual(pipeline.calls[0]["resume_task_id"], None)
        self.assertIn("highlight_commerce_v2_result.json", stdout.getvalue())
        self.assertIn("task-001", stdout.getvalue())

    def test_main_passes_resume_task_id_to_pipeline(self) -> None:
        class FakePipeline:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def run(self, asset: dict[str, object], **kwargs: object) -> dict[str, object]:
                self.calls.append({"asset": asset, **kwargs})
                return {
                    **asset,
                    "pipeline_version": "highlight_commerce_v2",
                    "render": {
                        "provider_job_id": kwargs["resume_task_id"],
                        "render_status": "running",
                    },
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset_path = root / "asset.json"
            output_root = root / "output"
            asset_path.write_text(json.dumps({"campaign_id": "case1"}), encoding="utf-8")
            pipeline = FakePipeline()

            exit_code = main(
                [
                    "--asset",
                    str(asset_path),
                    "--output-root",
                    str(output_root),
                    "--resume-task-id",
                    "task-existing",
                ],
                pipeline=pipeline,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(pipeline.calls[0]["resume_task_id"], "task-existing")


if __name__ == "__main__":
    unittest.main()

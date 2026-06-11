from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stdout

from scripts.highlight_commerce.run_seedance_render import main


class HighlightCommerceGenerationScriptTest(unittest.TestCase):
    def test_main_loads_asset_runs_pipeline_and_writes_result(self) -> None:
        class FakePipeline:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def run(self, asset: dict[str, object], *, output_dir: Path) -> dict[str, object]:
                self.calls.append({"asset": asset, "output_dir": output_dir})
                return {
                    **asset,
                    "render": {
                        "provider": "volcengine_seedance",
                        "provider_job_id": "task-001",
                        "render_status": "queued",
                    },
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset_path = root / "asset.json"
            output_root = root / "output"
            asset = {"campaign_id": "case1", "asset_type": "highlight_commerce_clip"}
            asset_path.write_text(json.dumps(asset), encoding="utf-8")
            pipeline = FakePipeline()

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--asset",
                        str(asset_path),
                        "--output-root",
                        str(output_root),
                    ],
                    pipeline=pipeline,
                )

            output_path = output_root / "case1" / "highlight_commerce_render.json"
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertIn(str(output_path), stdout.getvalue())
        self.assertEqual(payload["render"]["provider_job_id"], "task-001")
        self.assertEqual(pipeline.calls[0]["output_dir"], output_root / "case1")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pipelines.highlight_commerce.v2_pipeline import HighlightCommerceV2Pipeline


def _asset(root: Path) -> dict[str, object]:
    product = root / "product.jpg"
    product.write_bytes(b"product")
    return {
        "campaign_id": "kiss_breath_freshener_001",
        "target_duration_sec": 12,
        "product": {
            "product_name": "近距离清新好物",
            "category": "口喷",
            "image_path": str(product),
            "selling_points": ["随时清新", "近距离也安心"],
            "must_avoid": ["治疗口臭"],
        },
        "highlight": {
            "hook_description": "亲吻后的暧昧收尾。",
            "continuity_goal": "自然引出口喷。",
        },
        "seedance_request_plan": {
            "duration": 12,
            "reference_images": [{"role": "product", "path": str(product)}],
            "reference_audio": [],
        },
    }


def _scripted_asset(asset: dict[str, object]) -> dict[str, object]:
    return {
        **asset,
        "storyboard": [
            {
                "shot_id": "shot_001_highlight_hook",
                "start_sec": 0.0,
                "end_sec": 2.0,
                "description": "承接亲吻收尾。",
                "visual_prompt": "kiss ending",
                "dialogue": [],
                "product_visibility": "none",
            },
            {
                "shot_id": "shot_002_male_reaction",
                "start_sec": 2.0,
                "end_sec": 4.0,
                "description": "男主惊讶。",
                "visual_prompt": "male surprised",
                "dialogue": [{"speaker": "male_lead", "text": "怎么这么香。"}],
                "product_visibility": "none",
            },
        ],
        "generated_script": {
            "source": "llm",
            "hook_strategy": "从亲吻切入口喷。",
            "product_mentions": ["随时清新"],
            "avoid_claims": ["治疗口臭"],
            "seedance_prompt_notes": ["不要像硬广。"],
        },
    }


class HighlightCommerceV2PipelineTest(unittest.TestCase):
    def test_pipeline_runs_script_cartoon_and_seedance_then_writes_artifacts(self) -> None:
        class FakeScriptPipeline:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def run(self, asset: dict[str, object]) -> dict[str, object]:
                self.calls.append(asset)
                return _scripted_asset(asset)

        class FakeCartoonPipeline:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def run(self, asset: dict[str, object], *, output_dir: Path) -> dict[str, object]:
                self.calls.append({"asset": asset, "output_dir": output_dir})
                return {**asset, "cartoon_references": {"highlight_reference_path": str(output_dir / "cartoon.png")}}

        class FakeSeedancePipeline:
            def __init__(self) -> None:
                self.run_calls: list[dict[str, object]] = []

            def run(self, asset: dict[str, object], *, output_dir: Path) -> dict[str, object]:
                self.run_calls.append({"asset": asset, "output_dir": output_dir})
                return {
                    **asset,
                    "render": {
                        "provider_job_id": "task-001",
                        "render_status": "succeeded",
                        "output_video_path": str(output_dir / "highlight_commerce_seedance.mp4"),
                    },
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_dir = root / "output"
            script_pipeline = FakeScriptPipeline()
            cartoon_pipeline = FakeCartoonPipeline()
            seedance_pipeline = FakeSeedancePipeline()
            pipeline = HighlightCommerceV2Pipeline(
                script_pipeline=script_pipeline,
                cartoon_pipeline=cartoon_pipeline,
                seedance_pipeline=seedance_pipeline,
            )

            result = pipeline.run(_asset(root), output_dir=output_dir)

            script_payload = json.loads((output_dir / "highlight_commerce_script.json").read_text(encoding="utf-8"))
            cartoon_payload = json.loads((output_dir / "highlight_commerce_cartoon_asset.json").read_text(encoding="utf-8"))
            result_payload = json.loads((output_dir / "highlight_commerce_v2_result.json").read_text(encoding="utf-8"))

        self.assertEqual(len(script_pipeline.calls), 1)
        self.assertEqual(len(cartoon_pipeline.calls), 1)
        self.assertEqual(len(seedance_pipeline.run_calls), 1)
        self.assertEqual(script_payload["storyboard"][1]["dialogue"][0]["text"], "怎么这么香。")
        self.assertEqual(cartoon_payload["cartoon_references"]["highlight_reference_path"], str(output_dir / "cartoon.png"))
        self.assertEqual(result["render"]["provider_job_id"], "task-001")
        self.assertEqual(result_payload["pipeline_version"], "highlight_commerce_v2")

    def test_pipeline_can_resume_existing_seedance_task_without_recreating_script_or_cartoon(self) -> None:
        class FailingScriptPipeline:
            def run(self, asset: dict[str, object]) -> dict[str, object]:
                raise AssertionError("script generation should be skipped")

        class FailingCartoonPipeline:
            def run(self, asset: dict[str, object], *, output_dir: Path) -> dict[str, object]:
                raise AssertionError("cartoon generation should be skipped")

        class FakeSeedancePipeline:
            def __init__(self) -> None:
                self.resume_calls: list[dict[str, object]] = []

            def update_existing_task(self, asset: dict[str, object], *, task_id: str, output_dir: Path) -> dict[str, object]:
                self.resume_calls.append({"asset": asset, "task_id": task_id, "output_dir": output_dir})
                return {
                    **asset,
                    "render": {
                        "provider_job_id": task_id,
                        "render_status": "succeeded",
                        "output_video_path": str(output_dir / "highlight_commerce_seedance.mp4"),
                    },
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_dir = root / "output"
            output_dir.mkdir()
            cartoon_asset = {**_scripted_asset(_asset(root)), "cartoon_references": {"highlight_reference_path": "cartoon.png"}}
            (output_dir / "highlight_commerce_cartoon_asset.json").write_text(
                json.dumps(cartoon_asset, ensure_ascii=False),
                encoding="utf-8",
            )
            seedance_pipeline = FakeSeedancePipeline()
            pipeline = HighlightCommerceV2Pipeline(
                script_pipeline=FailingScriptPipeline(),
                cartoon_pipeline=FailingCartoonPipeline(),
                seedance_pipeline=seedance_pipeline,
            )

            result = pipeline.run(
                _asset(root),
                output_dir=output_dir,
                resume_task_id="task-existing",
            )

        self.assertEqual(seedance_pipeline.resume_calls[0]["task_id"], "task-existing")
        self.assertEqual(result["render"]["render_status"], "succeeded")


if __name__ == "__main__":
    unittest.main()

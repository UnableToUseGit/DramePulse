from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipelines.highlight_commerce.generation import (
    HighlightCommerceSeedancePipeline,
    build_highlight_commerce_prompt,
    ensure_reference_audio_clips,
    generate_privacy_safe_cartoon_references,
)
from pipelines.highlight_commerce.seedream_generation import SeedreamGenerationResult
from pipelines.highlight_commerce.seedance_generation import SeedanceTaskResult


def _asset(root: Path) -> dict[str, object]:
    highlight = root / "highlight.png"
    male = root / "male.png"
    female = root / "female.png"
    product = root / "product.jpg"
    male_audio = root / "male.mp3"
    female_audio = root / "female.mp3"
    for path in [highlight, male, female, product, male_audio, female_audio]:
        path.write_bytes(path.name.encode("utf-8"))
    return {
        "campaign_id": "kiss_breath_freshener_001",
        "target_duration_sec": 12,
        "source_assets": {
            "highlight_image_path": str(highlight),
            "male_character_image_path": str(male),
            "female_character_image_path": str(female),
            "product_image_path": str(product),
            "male_voice_reference_path": str(male_audio),
            "female_voice_reference_path": str(female_audio),
        },
        "seedance_request_plan": {
            "model": "doubao-seedance-2-0-260128",
            "ratio": "9:16",
            "duration": 12,
            "generate_audio": True,
            "watermark": False,
            "reference_images": [
                {"role": "highlight_scene", "path": str(highlight), "instruction": "高光氛围"},
                {"role": "male_character", "path": str(male), "instruction": "男主形象"},
                {"role": "female_character", "path": str(female), "instruction": "女主形象"},
                {"role": "product", "path": str(product), "instruction": "商品外观"},
            ],
            "reference_audio": [
                {
                    "speaker": "male_lead",
                    "source_path": str(male_audio),
                    "trim_start_sec": 0.0,
                    "trim_end_sec": 5.0,
                    "role": "reference_audio",
                },
                {
                    "speaker": "female_lead",
                    "source_path": str(female_audio),
                    "trim_start_sec": 0.0,
                    "trim_end_sec": 8.0,
                    "role": "reference_audio",
                },
            ],
            "prompt_notes": ["第一镜头必须承接高光亲吻收尾。"],
        },
        "highlight": {
            "hook_description": "亲吻后的暧昧收尾。",
            "continuity_goal": "自然引出口气清新需求。",
        },
        "product": {
            "product_name": "近距离清新好物",
            "category": "口喷",
            "image_path": str(product),
            "selling_points": ["随时清新", "近距离也安心"],
            "must_avoid": ["医疗功效"],
        },
        "storyboard": [
            {
                "shot_id": "shot_001_highlight_hook",
                "start_sec": 0,
                "end_sec": 2,
                "description": "两人亲吻收尾。",
                "visual_prompt": "kiss ending",
                "dialogue": [],
            },
            {
                "shot_id": "shot_002_male_reaction",
                "start_sec": 2,
                "end_sec": 4,
                "description": "男主微怔。",
                "visual_prompt": "male surprised",
                "dialogue": [{"speaker": "male_lead", "text": "怎么这么香。"}],
            },
        ],
    }


class HighlightCommerceGenerationTest(unittest.TestCase):
    def test_build_prompt_contains_highlight_and_exact_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            asset = _asset(Path(tmpdir))

            prompt = build_highlight_commerce_prompt(asset)

        self.assertIn("亲吻后的暧昧收尾", prompt)
        self.assertIn("怎么这么香。", prompt)
        self.assertIn("第一镜头必须承接高光亲吻收尾", prompt)
        self.assertIn("不要生成电商直播背景", prompt)

    def test_ensure_reference_audio_clips_runs_ffmpeg_for_each_audio(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> None:
            calls.append(command)
            Path(command[-1]).write_bytes(b"trimmed")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset = _asset(root)
            output_dir = root / "output"

            paths = ensure_reference_audio_clips(asset, output_dir=output_dir, command_runner=fake_runner)
            first_audio_bytes = paths[0].read_bytes()

        self.assertEqual(
            paths,
            [
                output_dir / "male_lead_reference_audio.mp3",
                output_dir / "female_lead_reference_audio.mp3",
            ],
        )
        self.assertEqual(len(calls), 2)
        self.assertIn("-to", calls[0])
        self.assertEqual(first_audio_bytes, b"trimmed")

    def test_pipeline_creates_seedance_task_with_images_and_audio(self) -> None:
        class FakeSeedanceClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def create_task(self, *, model: str, content: list[dict[str, object]], **kwargs: object) -> SeedanceTaskResult:
                self.calls.append({"model": model, "content": content, **kwargs})
                return SeedanceTaskResult(task_id="task-001", status="queued")

        def fake_runner(command: list[str]) -> None:
            Path(command[-1]).write_bytes(b"trimmed")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset = _asset(root)
            client = FakeSeedanceClient()
            pipeline = HighlightCommerceSeedancePipeline(
                seedance_client=client,
                wait_for_completion=False,
                command_runner=fake_runner,
            )

            result = pipeline.run(asset, output_dir=root / "output")

        self.assertEqual(result["render"]["provider_job_id"], "task-001")
        call = client.calls[0]
        self.assertEqual(call["model"], "doubao-seedance-2-0-260128")
        self.assertEqual(call["duration"], 12)
        self.assertEqual(call["ratio"], "9:16")
        self.assertEqual(call["generate_audio"], True)
        self.assertEqual(sum(1 for item in call["content"] if item["type"] == "image_url"), 4)
        self.assertEqual(sum(1 for item in call["content"] if item["type"] == "audio_url"), 2)

    def test_pipeline_can_resume_existing_seedance_task_and_download_video(self) -> None:
        class FakeSeedanceClient:
            def __init__(self) -> None:
                self.get_calls: list[str] = []

            def get_task(self, task_id: str) -> SeedanceTaskResult:
                self.get_calls.append(task_id)
                return SeedanceTaskResult(
                    task_id=task_id,
                    status="succeeded",
                    video_url="https://example.test/output.mp4",
                )

        class FakeHttpClient:
            def get(self, url: str, timeout: int) -> object:
                class Response:
                    content = b"video-bytes"

                    def raise_for_status(self) -> None:
                        return None

                return Response()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset = _asset(root)
            client = FakeSeedanceClient()
            pipeline = HighlightCommerceSeedancePipeline(
                seedance_client=client,
                wait_for_completion=False,
                http_client=FakeHttpClient(),
            )

            result = pipeline.update_existing_task(
                asset,
                task_id="task-existing",
                output_dir=root / "output",
            )
            video_bytes = Path(result["render"]["output_video_path"]).read_bytes()

        self.assertEqual(client.get_calls, ["task-existing"])
        self.assertEqual(result["render"]["render_status"], "succeeded")
        self.assertEqual(result["render"]["output_video_url"], "https://example.test/output.mp4")
        self.assertEqual(video_bytes, b"video-bytes")

    def test_generate_privacy_safe_cartoon_references_creates_highlight_and_character_assets(self) -> None:
        class FakeSeedreamClient:
            def __init__(self) -> None:
                self.calls: list[object] = []

            def generate_image(self, request: object) -> SeedreamGenerationResult:
                self.calls.append(request)
                return SeedreamGenerationResult(url=f"https://example.test/{len(self.calls)}.png")

        class FakeHttpClient:
            def get(self, url: str, timeout: int) -> object:
                class Response:
                    content = f"downloaded:{url}".encode("utf-8")

                    def raise_for_status(self) -> None:
                        return None

                return Response()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset = _asset(root)
            style_1 = root / "style_1.png"
            style_2 = root / "style_2.png"
            style_1.write_bytes(b"style-1")
            style_2.write_bytes(b"style-2")
            client = FakeSeedreamClient()

            safe_asset = generate_privacy_safe_cartoon_references(
                asset,
                output_dir=root / "output",
                style_reference_paths=[style_1, style_2],
                seedream_client=client,
                http_client=FakeHttpClient(),
            )
            cartoon_refs = safe_asset["cartoon_references"]
            highlight_exists = Path(cartoon_refs["highlight_reference_path"]).exists()
            male_exists = Path(cartoon_refs["male_avatar_path"]).exists()
            female_exists = Path(cartoon_refs["female_avatar_path"]).exists()

        self.assertEqual(len(client.calls), 3)
        self.assertTrue(highlight_exists)
        self.assertTrue(male_exists)
        self.assertTrue(female_exists)
        first_request = client.calls[0]
        self.assertEqual(first_request.reference_image_paths[0], Path(asset["seedance_request_plan"]["reference_images"][0]["path"]))  # type: ignore[index]
        self.assertEqual(first_request.reference_image_paths[1:], [style_1, style_2])
        reference_images = safe_asset["seedance_request_plan"]["reference_images"]
        self.assertEqual(
            [item["role"] for item in reference_images],
            ["cartoon_highlight_reference", "cartoon_male_avatar", "cartoon_female_avatar", "product"],
        )


if __name__ == "__main__":
    unittest.main()

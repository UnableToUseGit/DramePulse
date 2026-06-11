from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipelines.highlight_commerce.script_generation import (
    HighlightCommerceScriptGenerationPipeline,
    apply_highlight_commerce_script,
    validate_highlight_commerce_script,
)


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
        "highlight": {
            "hook_description": "亲吻后的暧昧收尾。",
            "continuity_goal": "自然引出口气清新需求。",
        },
        "product": {
            "product_name": "近距离清新好物",
            "category": "口喷",
            "image_path": str(product),
            "selling_points": ["随时清新", "近距离也安心", "小巧便携"],
            "must_avoid": ["治疗口臭", "医疗功效", "永久清新", "绝对化承诺"],
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
                {"speaker": "male_lead", "source_path": str(male_audio), "trim_start_sec": 0.0, "trim_end_sec": 5.0},
                {"speaker": "female_lead", "source_path": str(female_audio), "trim_start_sec": 0.0, "trim_end_sec": 8.0},
            ],
            "prompt_notes": ["保持短剧画面质感。"],
        },
    }


def _script() -> dict[str, object]:
    return {
        "hook_strategy": "前 2 秒承接亲吻收尾，用男主近距离反应自然引出口喷。",
        "storyboard": [
            {
                "shot_id": "shot_001_highlight_hook",
                "start_sec": 0.0,
                "end_sec": 2.0,
                "description": "两人亲吻收尾。",
                "visual_prompt": "romantic close-distance kiss ending",
                "dialogue": [],
                "product_visibility": "none",
            },
            {
                "shot_id": "shot_002_male_reaction",
                "start_sec": 2.0,
                "end_sec": 4.0,
                "description": "男主微怔，略带惊讶。",
                "visual_prompt": "male lead surprised close-up",
                "dialogue": [{"speaker": "male_lead", "text": "怎么这么香。"}],
                "product_visibility": "none",
            },
            {
                "shot_id": "shot_003_female_bridge",
                "start_sec": 4.0,
                "end_sec": 7.0,
                "description": "女主拿出口喷。",
                "visual_prompt": "female lead presents breath spray",
                "dialogue": [{"speaker": "female_lead", "text": "亲密时刻，当然不能掉链子。"}],
                "product_visibility": "medium",
            },
            {
                "shot_id": "shot_004_product_closeup",
                "start_sec": 7.0,
                "end_sec": 9.0,
                "description": "产品特写。",
                "visual_prompt": "clean product close-up",
                "dialogue": [],
                "on_screen_text": ["随时清新", "近距离也安心"],
                "product_visibility": "high",
            },
            {
                "shot_id": "shot_005_character_close",
                "start_sec": 9.0,
                "end_sec": 12.0,
                "description": "女主收口。",
                "visual_prompt": "female lead final line",
                "dialogue": [{"speaker": "female_lead", "text": "想靠近，就别让口气拖后腿。"}],
                "product_visibility": "medium",
            },
        ],
        "product_mentions": ["随时清新", "近距离也安心"],
        "avoid_claims": ["治疗口臭", "医疗功效", "永久清新", "绝对化承诺"],
        "seedance_prompt_notes": ["第一镜头必须承接高光，不要像硬广。"],
    }


class HighlightCommerceScriptGenerationTest(unittest.TestCase):
    def test_validate_highlight_commerce_script_accepts_llm_storyboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            asset = _asset(Path(tmpdir))
            script = validate_highlight_commerce_script(_script(), asset=asset)

        self.assertEqual(script["hook_strategy"], "前 2 秒承接亲吻收尾，用男主近距离反应自然引出口喷。")
        self.assertEqual(len(script["storyboard"]), 5)
        self.assertEqual(script["storyboard"][1]["dialogue"][0]["text"], "怎么这么香。")

    def test_validate_highlight_commerce_script_rejects_forbidden_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            asset = _asset(Path(tmpdir))
            script = _script()
            script["storyboard"][2]["dialogue"][0]["text"] = "这个可以治疗口臭。"  # type: ignore[index]

            with self.assertRaisesRegex(ValueError, "forbidden claim"):
                validate_highlight_commerce_script(script, asset=asset)

    def test_apply_highlight_commerce_script_updates_storyboard_and_prompt_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            asset = _asset(Path(tmpdir))
            updated = apply_highlight_commerce_script(asset, _script())

        self.assertEqual(updated["storyboard"][0]["shot_id"], "shot_001_highlight_hook")
        self.assertEqual(updated["storyboard"][1]["dialogue"][0]["text"], "怎么这么香。")
        self.assertIn("第一镜头必须承接高光，不要像硬广。", updated["seedance_request_plan"]["prompt_notes"])
        self.assertEqual(updated["generated_script"]["source"], "llm")

    def test_pipeline_uses_llm_output_and_reference_images(self) -> None:
        class FakeLlmClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def generate_json_multimodal(self, **kwargs: object) -> dict[str, object]:
                self.calls.append(kwargs)
                return {"highlight_commerce_script": _script()}

        with tempfile.TemporaryDirectory() as tmpdir:
            asset = _asset(Path(tmpdir))
            client = FakeLlmClient()
            pipeline = HighlightCommerceScriptGenerationPipeline(llm_client=client)

            updated = pipeline.run(asset)

        self.assertEqual(updated["storyboard"][4]["dialogue"][0]["speaker"], "female_lead")
        self.assertEqual(len(client.calls), 1)
        self.assertIn("Return only JSON", client.calls[0]["system_prompt"])
        self.assertEqual(len(client.calls[0]["image_paths"]), 4)

    def test_pipeline_repairs_invalid_llm_script_once(self) -> None:
        class FakeLlmClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def generate_json_multimodal(self, **kwargs: object) -> dict[str, object]:
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    invalid = _script()
                    invalid["storyboard"][2]["dialogue"][0]["text"] = "治疗口臭很有效。"  # type: ignore[index]
                    return invalid
                return _script()

        with tempfile.TemporaryDirectory() as tmpdir:
            asset = _asset(Path(tmpdir))
            client = FakeLlmClient()
            pipeline = HighlightCommerceScriptGenerationPipeline(llm_client=client)

            updated = pipeline.run(asset)

        self.assertEqual(len(client.calls), 2)
        self.assertIn("Repair the JSON", client.calls[1]["user_prompt"])
        self.assertEqual(updated["storyboard"][2]["dialogue"][0]["text"], "亲密时刻，当然不能掉链子。")


if __name__ == "__main__":
    unittest.main()

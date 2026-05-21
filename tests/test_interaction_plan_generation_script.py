from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_interaction_plan_generation import main


class InteractionPlanGenerationScriptTest(unittest.TestCase):
    def test_main_runs_pipeline_with_highlights_and_danmaku_then_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            output_root = root / "output"
            case_dir = data_root / "case1"
            highlight_output_dir = output_root / "case1_ep01"
            case_dir.mkdir(parents=True)
            highlight_output_dir.mkdir(parents=True)
            video_path = case_dir / "ep01.mp4"
            source_json_path = case_dir / "ep01.json"
            subtitle_path = case_dir / "ep01.srt"
            video_path.write_bytes(b"video")
            source_json_path.write_text(
                json.dumps(
                    {
                        "danmaku": [
                            {
                                "time_sec": 39.5,
                                "text": "这个反转绝了",
                                "digg_count": 88,
                                "score": 99.0,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            subtitle_path.write_text("1\n00:00:38,000 --> 00:00:39,000\n第一句\n", encoding="utf-8")
            highlight_output = {
                "video_id": "case1_ep01",
                "highlight_assets": [
                    {
                        "highlight_id": "h_case1_ep01_001",
                        "video_id": "case1_ep01",
                        "start_time": 38.0,
                        "end_time": 46.0,
                        "highlight_type": "身份揭露",
                        "emotion": "震惊",
                        "intensity": 0.92,
                        "summary": "男主真实身份曝光，反派震惊。",
                        "reason": "前文铺垫男主被轻视，此处身份反转。",
                        "confidence": 0.88,
                    }
                ],
            }
            (highlight_output_dir / "highlight_recognition.json").write_text(
                json.dumps(highlight_output, ensure_ascii=False),
                encoding="utf-8",
            )

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(
                    self,
                    *,
                    highlight_asset: dict[str, object],
                    video_file_path: Path,
                    subtitle_file_path: Path,
                    danmaku_items: list[dict[str, object]],
                ) -> dict[str, object]:
                    self.calls.append(
                        {
                            "highlight_asset": highlight_asset,
                            "video_file_path": video_file_path,
                            "subtitle_file_path": subtitle_file_path,
                            "danmaku_items": danmaku_items,
                        }
                    )
                    return {
                        "interaction_id": "i_h_case1_ep01_001",
                        "highlight_id": highlight_asset["highlight_id"],
                        "video_id": "case1_ep01",
                        "trigger_time": 38.0,
                        "expire_time": 46.0,
                        "interaction_type": "danmaku_poll",
                        "question": "这波反转你怎么看？",
                        "options": [
                            {
                                "option_id": "o_h_case1_ep01_001_001",
                                "text": "反转了",
                                "danmaku_text": "这也太反转了！",
                            },
                            {
                                "option_id": "o_h_case1_ep01_001_002",
                                "text": "爽到了",
                                "danmaku_text": "爽到了！",
                            },
                        ],
                        "feedback": {"type": "poll_result"},
                    }

            fake_pipeline = FakePipeline()
            result = main(
                [
                    "case1_ep01",
                    "--data-root",
                    str(data_root),
                    "--output-root",
                    str(output_root),
                ],
                pipeline=fake_pipeline,
            )

            output_file = output_root / "case1_ep01" / "interaction_plan_generation.json"
            self.assertEqual(result, 0)
            self.assertEqual(len(fake_pipeline.calls), 1)
            self.assertEqual(fake_pipeline.calls[0]["video_file_path"], video_path)
            self.assertEqual(fake_pipeline.calls[0]["subtitle_file_path"], subtitle_path)
            self.assertEqual(
                fake_pipeline.calls[0]["danmaku_items"],
                [{"time_sec": 39.5, "text": "这个反转绝了", "digg_count": 88, "score": 99.0}],
            )
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["video_id"], "case1_ep01")
            self.assertEqual(payload["video_path"], str(video_path))
            self.assertEqual(payload["source_json_path"], str(source_json_path))
            self.assertEqual(payload["subtitle_path"], str(subtitle_path))
            self.assertEqual(payload["highlight_recognition_path"], str(highlight_output_dir / "highlight_recognition.json"))
            self.assertEqual(payload["interaction_plans"][0]["interaction_id"], "i_h_case1_ep01_001")


if __name__ == "__main__":
    unittest.main()

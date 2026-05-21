from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_highlight_recognition import main, resolve_video_inputs


class ResolveVideoInputsTest(unittest.TestCase):
    def test_resolve_video_inputs_maps_case_episode_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            case_dir = data_root / "case1"
            case_dir.mkdir()
            (case_dir / "ep01.mp4").write_bytes(b"video")
            (case_dir / "ep01.json").write_text("{}", encoding="utf-8")
            (case_dir / "ep01.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n第一句\n", encoding="utf-8")

            resolved = resolve_video_inputs("case1_ep01", data_root=data_root)

            self.assertEqual(resolved.video_path, case_dir / "ep01.mp4")
            self.assertEqual(resolved.source_json_path, case_dir / "ep01.json")
            self.assertEqual(resolved.subtitle_path, case_dir / "ep01.srt")


class HighlightRecognitionScriptTest(unittest.TestCase):
    def test_main_runs_pipeline_and_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            output_root = root / "output"
            case_dir = data_root / "case1"
            case_dir.mkdir(parents=True)
            (case_dir / "ep01.mp4").write_bytes(b"video")
            (case_dir / "ep01.json").write_text('{"danmaku": []}', encoding="utf-8")
            (case_dir / "ep01.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n第一句\n", encoding="utf-8")

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run(self, *, video_id: str, video_file_path: Path, subtitle_file_path: Path) -> list[dict[str, object]]:
                    self.calls.append(
                        {
                            "video_id": video_id,
                            "video_file_path": video_file_path,
                            "subtitle_file_path": subtitle_file_path,
                        }
                    )
                    return [
                        {
                            "highlight_id": "h_case1_ep01_001",
                            "video_id": video_id,
                            "start_time": 0.0,
                            "end_time": 1.0,
                            "highlight_type": "冲突爆发",
                            "emotion": "愤怒",
                            "intensity": 0.7,
                            "summary": "冲突升级。",
                            "reason": "测试用高光。",
                            "confidence": 0.9,
                        }
                    ]

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

            output_file = output_root / "case1_ep01" / "highlight_recognition.json"
            self.assertEqual(result, 0)
            self.assertTrue(output_file.exists())
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["video_id"], "case1_ep01")
            self.assertEqual(payload["video_path"], str(case_dir / "ep01.mp4"))
            self.assertEqual(payload["source_json_path"], str(case_dir / "ep01.json"))
            self.assertEqual(payload["subtitle_path"], str(case_dir / "ep01.srt"))
            self.assertEqual(payload["highlight_assets"][0]["highlight_id"], "h_case1_ep01_001")


if __name__ == "__main__":
    unittest.main()

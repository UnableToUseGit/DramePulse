from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
    def test_main_loads_ark_config_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            output_root = root / "output"
            case_dir = data_root / "case1"
            case_dir.mkdir(parents=True)
            (case_dir / "ep01.mp4").write_bytes(b"video")
            (case_dir / "ep01.json").write_text('{"danmaku": []}', encoding="utf-8")
            (case_dir / "ep01.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n第一句\n", encoding="utf-8")
            env_file = root / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "ARK_BASE_URL=https://ark.example.com/api/v3",
                        "ARK_API_KEY=from-env-file",
                        "ARK_MODEL=demo-model",
                    ]
                ),
                encoding="utf-8",
            )

            captured_client_args: dict[str, object] = {}

            class FakeClient:
                def __init__(self, *, api_key: str | None = None, base_url: str | None = None, model_name: str | None = None, timeout_sec: int = 90) -> None:
                    captured_client_args.update(
                        {
                            "api_key": api_key,
                            "base_url": base_url,
                            "model_name": model_name,
                            "timeout_sec": timeout_sec,
                        }
                    )

            class FakePipeline:
                def __init__(self, *, llm_client: object) -> None:
                    self.llm_client = llm_client

                def run(self, *, video_id: str, video_file_path: Path, subtitle_file_path: Path) -> list[dict[str, object]]:
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

            with patch("scripts.run_highlight_recognition.VolcArkLlmClient", FakeClient), patch(
                "scripts.run_highlight_recognition.HighlightRecognitionPipeline",
                FakePipeline,
            ):
                result = main(
                    [
                        "case1_ep01",
                        "--data-root",
                        str(data_root),
                        "--output-root",
                        str(output_root),
                        "--env-file",
                        str(env_file),
                    ]
                )

            self.assertEqual(result, 0)
            self.assertEqual(captured_client_args["api_key"], "from-env-file")
            self.assertEqual(captured_client_args["base_url"], "https://ark.example.com/api/v3")
            self.assertEqual(captured_client_args["model_name"], "demo-model")

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

    def test_main_writes_expression_triggers_when_pipeline_supports_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            output_root = root / "output"
            case_dir = data_root / "case1"
            case_dir.mkdir(parents=True)
            (case_dir / "ep01.mp4").write_bytes(b"video")
            (case_dir / "ep01.json").write_text(
                json.dumps(
                    {
                        "title": "第 1 集",
                        "description": "女主反击",
                        "danmaku": [{"time_sec": 20.0, "text": "笑死"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (case_dir / "ep01.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n第一句\n", encoding="utf-8")

            class FakePipeline:
                def __init__(self) -> None:
                    self.calls: list[dict[str, object]] = []

                def run_expression_triggers(
                    self,
                    *,
                    video_id: str,
                    video_file_path: Path,
                    subtitle_file_path: Path,
                    metadata: dict[str, object],
                    danmaku_items: list[dict[str, object]],
                ) -> list[dict[str, object]]:
                    self.calls.append(
                        {
                            "metadata": metadata,
                            "danmaku_items": danmaku_items,
                        }
                    )
                    return [
                        {
                            "trigger_id": "et_case1_ep01_001",
                            "video_id": video_id,
                            "start_time": 0.0,
                            "end_time": 1.0,
                            "cue_time": 0.5,
                            "source_type": "plot",
                            "primary_expression": "爽到了",
                            "interaction_mode": "single_tap",
                            "intensity": 0.7,
                            "confidence": 0.9,
                            "summary": "女主反击。",
                            "reason": "适合表达爽感。",
                            "status": "verified",
                            "created_at": "2026-05-30T00:00:00Z",
                            "updated_at": "2026-05-30T00:00:00Z",
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
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(payload["expression_triggers"][0]["trigger_id"], "et_case1_ep01_001")
            self.assertEqual(payload["highlight_assets"][0]["highlight_type"], "plot")
            self.assertEqual(payload["highlight_assets"][0]["emotion"], "爽到了")
            self.assertEqual(fake_pipeline.calls[0]["metadata"]["title"], "第 1 集")
            self.assertEqual(fake_pipeline.calls[0]["danmaku_items"][0]["text"], "笑死")


if __name__ == "__main__":
    unittest.main()

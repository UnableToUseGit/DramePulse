from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def make_episode(data_root: Path, *, series_id: str, episode_id: str) -> None:
    episode_dir = data_root / series_id / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(b"video")
    (episode_dir / "video.srt").write_text("1\n00:00:05,000 --> 00:00:08,000\n你终于输了\n", encoding="utf-8")
    (episode_dir / "douyin.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "title": f"{series_id} {episode_id}",
                    "series": {"name": "测试短剧", "current_episode": 1},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_text_batch_main_writes_review_tool_compatible_outputs(tmp_path: Path) -> None:
    from scripts.run_text_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")

    class FakePipeline:
        last_llm_call = {
            "status": "success",
            "elapsed_sec": 0.25,
            "usage": {"total_tokens": 42},
        }

        def run(
            self,
            *,
            video_id: str,
            subtitle_file_path: Path,
            metadata: dict[str, object],
        ) -> list[dict[str, object]]:
            self.call = {
                "video_id": video_id,
                "subtitle_file_path": subtitle_file_path,
                "metadata": metadata,
            }
            return [
                {
                    "trigger_id": f"et_{video_id}_001",
                    "video_id": video_id,
                    "start_time": 5.0,
                    "end_time": 8.0,
                    "cue_time": 7.0,
                    "source_type": "plot",
                    "primary_expression": "爽到了",
                    "interaction_mode": "single_tap",
                    "intensity": 0.8,
                    "confidence": 0.9,
                    "summary": "女主反击。",
                    "setup": "女主此前被压制。",
                    "turning_point": "女主当前反击。",
                    "expression_release": "压抑释放形成爽感。",
                    "reason": "适合表达爽感。",
                }
            ]

    fake_pipeline = FakePipeline()

    result = main(
        [
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
        ],
        pipeline=fake_pipeline,
    )

    output_path = output_root / "series_a_ep01" / "highlight_recognition.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["video_id"] == "series_a_ep01"
    assert payload["expression_triggers"][0]["primary_expression"] == "爽到了"
    assert payload["highlight_assets"][0]["emotion"] == "爽到了"
    assert payload["llm_call"]["usage"]["total_tokens"] == 42
    assert fake_pipeline.call["subtitle_file_path"] == data_root / "series_a" / "ep01" / "video.srt"
    assert fake_pipeline.call["metadata"]["title"] == "series_a ep01"


def test_text_batch_main_accepts_exact_video_ids(tmp_path: Path) -> None:
    from scripts.run_text_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_a", episode_id="ep02")

    class FakePipeline:
        last_llm_call: dict[str, object] = {}

        def __init__(self) -> None:
            self.video_ids: list[str] = []

        def run(self, **kwargs: object) -> list[dict[str, object]]:
            self.video_ids.append(str(kwargs["video_id"]))
            return []

    fake_pipeline = FakePipeline()

    result = main(
        [
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
            "--video-id",
            "series_a_ep02",
        ],
        pipeline=fake_pipeline,
    )

    assert result == 0
    assert fake_pipeline.video_ids == ["series_a_ep02"]

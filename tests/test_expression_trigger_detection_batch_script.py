from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def make_episode(data_root: Path, *, series_id: str, episode_id: str, with_danmaku: bool = True) -> Path:
    episode_dir = data_root / series_id / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(b"video")
    (episode_dir / "video.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n第一句\n", encoding="utf-8")
    if with_danmaku:
        (episode_dir / "douyin.json").write_text(
            json.dumps(
                {
                    "metadata": {
                        "title": f"{series_id} {episode_id}",
                        "duration_ms": 120000,
                        "series": {"name": "测试短剧", "current_episode": 1},
                    },
                    "danmaku": {
                        "items": [
                            {"time_sec": 1.2, "text": "笑死"},
                            {"time_ms": 2500, "text": "太帅了"},
                        ]
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return episode_dir


def write_danmaku_csv(data_root: Path) -> Path:
    data_root.mkdir(parents=True, exist_ok=True)
    path = data_root / "圈选剧前5集弹幕.csv"
    path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,1500,3,CSV弹幕更全",
                "北往,第2集,2500,1,第二集弹幕",
            ]
        )
        + "\n",
        encoding="gb18030",
    )
    return path


def test_discover_episodes_scans_dataset_shape_with_filters_and_limit(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import discover_episodes

    data_root = tmp_path / "DataForAlgorithm"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_a", episode_id="ep02")
    make_episode(data_root, series_id="series_b", episode_id="ep01")

    episodes = discover_episodes(data_root=data_root, series_id="series_a", episode_id=None, limit=1)

    assert len(episodes) == 1
    assert episodes[0].video_id == "series_a_ep01"
    assert episodes[0].video_path == data_root / "series_a" / "ep01" / "video.mp4"
    assert episodes[0].subtitle_path == data_root / "series_a" / "ep01" / "video.srt"
    assert episodes[0].source_json_path == data_root / "series_a" / "ep01" / "douyin.json"


def test_discover_episodes_filters_multiple_series_ids(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import discover_episodes

    data_root = tmp_path / "DataForAlgorithm"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_b", episode_id="ep01")
    make_episode(data_root, series_id="series_c", episode_id="ep01")

    episodes = discover_episodes(
        data_root=data_root,
        series_ids=["series_a", "series_c"],
    )

    assert [episode.video_id for episode in episodes] == ["series_a_ep01", "series_c_ep01"]


def test_discover_episodes_filters_multiple_episode_ids(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import discover_episodes

    data_root = tmp_path / "DataForAlgorithm"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_a", episode_id="ep02")
    make_episode(data_root, series_id="series_a", episode_id="ep03")

    episodes = discover_episodes(
        data_root=data_root,
        series_ids=["series_a"],
        episode_ids=["ep01", "ep02"],
    )

    assert [episode.video_id for episode in episodes] == ["series_a_ep01", "series_a_ep02"]


def test_discover_episodes_filters_exact_video_ids(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import discover_episodes

    data_root = tmp_path / "DataForAlgorithm"
    make_episode(data_root, series_id="beiwang", episode_id="ep01")
    make_episode(data_root, series_id="beiwang", episode_id="ep02")
    make_episode(data_root, series_id="nanian_dongzhi", episode_id="ep01")
    make_episode(data_root, series_id="nanian_dongzhi", episode_id="ep03")

    episodes = discover_episodes(
        data_root=data_root,
        video_ids=["beiwang_ep02", "nanian_dongzhi_ep01"],
    )

    assert [episode.video_id for episode in episodes] == ["beiwang_ep02", "nanian_dongzhi_ep01"]


def test_batch_main_writes_expression_trigger_outputs_for_dataset_episodes(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")

    class FakePipeline:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.last_llm_call = {
                "status": "success",
                "elapsed_sec": 1.25,
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

        def run(
            self,
            *,
            video_id: str,
            video_file_path: Path,
            subtitle_file_path: Path,
            metadata: dict[str, object],
            danmaku_items: list[dict[str, object]],
            include_finale_trigger: bool,
        ) -> list[dict[str, object]]:
            self.calls.append(
                {
                    "video_id": video_id,
                    "metadata": metadata,
                    "danmaku_items": danmaku_items,
                    "include_finale_trigger": include_finale_trigger,
                }
            )
            return [
                {
                    "trigger_id": f"et_{video_id}_001",
                    "video_id": video_id,
                    "start_time": 1.0,
                    "end_time": 2.0,
                    "cue_time": 1.5,
                    "source_type": "plot",
                    "primary_expression": "爽到了",
                    "interaction_mode": "single_tap",
                    "intensity": 0.8,
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
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
            "--include-finale-trigger",
        ],
        pipeline=fake_pipeline,
    )

    output_path = output_root / "series_a_ep01" / "highlight_recognition.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["video_id"] == "series_a_ep01"
    assert payload["video_path"] == str(data_root / "series_a" / "ep01" / "video.mp4")
    assert payload["source_json_path"] == str(data_root / "series_a" / "ep01" / "douyin.json")
    assert payload["expression_triggers"][0]["trigger_id"] == "et_series_a_ep01_001"
    assert payload["highlight_assets"][0]["highlight_type"] == "plot"
    assert payload["llm_call"]["status"] == "success"
    assert payload["llm_call"]["usage"]["total_tokens"] == 15
    assert fake_pipeline.calls[0]["metadata"]["title"] == "series_a ep01"
    assert fake_pipeline.calls[0]["danmaku_items"][1]["time_sec"] == 2.5
    assert fake_pipeline.calls[0]["include_finale_trigger"] is True


def test_batch_main_accepts_multiple_series_ids(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_b", episode_id="ep01")
    make_episode(data_root, series_id="series_c", episode_id="ep01")

    class FakePipeline:
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
            "--series-id",
            "series_a",
            "series_c",
        ],
        pipeline=fake_pipeline,
    )

    assert result == 0
    assert fake_pipeline.video_ids == ["series_a_ep01", "series_c_ep01"]
    assert not (output_root / "series_b_ep01" / "highlight_recognition.json").exists()


def test_batch_main_accepts_repeated_series_id_arguments(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_b", episode_id="ep01")
    make_episode(data_root, series_id="series_c", episode_id="ep01")

    class FakePipeline:
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
            "--series-id",
            "series_a",
            "--series-id",
            "series_c",
        ],
        pipeline=fake_pipeline,
    )

    assert result == 0
    assert fake_pipeline.video_ids == ["series_a_ep01", "series_c_ep01"]


def test_batch_main_accepts_multiple_episode_ids(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_a", episode_id="ep02")
    make_episode(data_root, series_id="series_a", episode_id="ep03")

    class FakePipeline:
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
            "--series-id",
            "series_a",
            "--episode-id",
            "ep01",
            "ep02",
        ],
        pipeline=fake_pipeline,
    )

    assert result == 0
    assert fake_pipeline.video_ids == ["series_a_ep01", "series_a_ep02"]


def test_batch_main_accepts_exact_video_ids(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="beiwang", episode_id="ep01")
    make_episode(data_root, series_id="beiwang", episode_id="ep02")
    make_episode(data_root, series_id="nanian_dongzhi", episode_id="ep01")
    make_episode(data_root, series_id="nanian_dongzhi", episode_id="ep03")

    class FakePipeline:
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
            "beiwang_ep02",
            "nanian_dongzhi_ep01",
        ],
        pipeline=fake_pipeline,
    )

    assert result == 0
    assert fake_pipeline.video_ids == ["beiwang_ep02", "nanian_dongzhi_ep01"]


def test_build_pipeline_can_disable_danmaku_enhancement() -> None:
    from scripts.run_expression_trigger_detection_batch import build_pipeline

    class FakePipeline:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeClient:
        pass

    import scripts.run_expression_trigger_detection_batch as batch

    original_client_builder = batch.build_llm_client
    original_pipeline = None
    try:
        batch.build_llm_client = lambda *, env_path: FakeClient()  # type: ignore[assignment]
        from pipelines import expression_trigger_detection

        original_pipeline = expression_trigger_detection.ExpressionTriggerPipeline
        expression_trigger_detection.ExpressionTriggerPipeline = FakePipeline  # type: ignore[assignment]

        pipeline = build_pipeline(
            env_path=Path(".env"),
            sample_interval_sec=1.0,
            frames_per_interval=1,
            max_frames=3,
            enable_danmaku_enhancement=False,
        )
    finally:
        batch.build_llm_client = original_client_builder  # type: ignore[assignment]
        if original_pipeline is not None:
            expression_trigger_detection.ExpressionTriggerPipeline = original_pipeline  # type: ignore[assignment]

    assert isinstance(pipeline, FakePipeline)
    assert pipeline.kwargs["enable_danmaku_enhancement"] is False


def test_build_llm_client_defaults_to_ark_with_generic_env_values(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import build_llm_client

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "API_KEY=generic-key",
                "BASE_URL=https://llm.example/api/v3",
                "MODEL=generic-model",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeArkClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    with patch("scripts.run_expression_trigger_detection_batch.VolcArkLlmClient", FakeArkClient):
        client = build_llm_client(env_path=env_path)

    assert isinstance(client, FakeArkClient)
    assert client.kwargs == {
        "api_key": "generic-key",
        "base_url": "https://llm.example/api/v3",
        "model_name": "generic-model",
    }


def test_build_llm_client_selects_openai_with_generic_env_values(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import build_llm_client

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=openai",
                "API_KEY=generic-key",
                "BASE_URL=https://llm.example/v1",
                "MODEL=gpt-test",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeOpenAiClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    with patch("scripts.run_expression_trigger_detection_batch.OpenAiLlmClient", FakeOpenAiClient):
        client = build_llm_client(env_path=env_path)

    assert isinstance(client, FakeOpenAiClient)
    assert client.kwargs == {
        "api_key": "generic-key",
        "base_url": "https://llm.example/v1",
        "model_name": "gpt-test",
    }


def test_batch_main_prefers_root_csv_danmaku_over_douyin_json(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    write_danmaku_csv(data_root)
    make_episode(data_root, series_id="beiwang", episode_id="ep01")

    class FakePipeline:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(
            self,
            *,
            video_id: str,
            video_file_path: Path,
            subtitle_file_path: Path,
            metadata: dict[str, object],
            danmaku_items: list[dict[str, object]],
            include_finale_trigger: bool,
        ) -> list[dict[str, object]]:
            self.calls.append({"video_id": video_id, "danmaku_items": danmaku_items})
            return []

    fake_pipeline = FakePipeline()

    result = main(["--data-root", str(data_root), "--output-root", str(output_root)], pipeline=fake_pipeline)

    assert result == 0
    assert fake_pipeline.calls[0]["video_id"] == "beiwang_ep01"
    assert fake_pipeline.calls[0]["danmaku_items"][0]["text"] == "CSV弹幕更全"
    assert fake_pipeline.calls[0]["danmaku_items"][0]["time_sec"] == 1.5
    assert fake_pipeline.calls[0]["danmaku_items"][0]["digg_count"] == 3


def test_batch_main_skips_existing_outputs_unless_force(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    output_path = output_root / "series_a_ep01" / "highlight_recognition.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text('{"video_id": "series_a_ep01", "existing": true}\n', encoding="utf-8")

    class FakePipeline:
        def run(self, **kwargs: object) -> list[dict[str, object]]:
            raise AssertionError("pipeline should not run when output exists without --force")

    result = main(["--data-root", str(data_root), "--output-root", str(output_root)], pipeline=FakePipeline())

    assert result == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["existing"] is True


def test_batch_main_continues_after_episode_failure_and_returns_nonzero(tmp_path: Path) -> None:
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_a", episode_id="ep02")

    class FakePipeline:
        def run(
            self,
            *,
            video_id: str,
            video_file_path: Path,
            subtitle_file_path: Path,
            metadata: dict[str, object],
            danmaku_items: list[dict[str, object]],
            include_finale_trigger: bool,
        ) -> list[dict[str, object]]:
            if video_id.endswith("ep01"):
                raise RuntimeError("model failed")
            return [
                {
                    "trigger_id": f"et_{video_id}_001",
                    "video_id": video_id,
                    "start_time": 1.0,
                    "end_time": 2.0,
                    "cue_time": 1.5,
                    "source_type": "plot",
                    "primary_expression": "震惊",
                    "interaction_mode": "single_tap",
                    "intensity": 0.7,
                    "confidence": 0.8,
                    "summary": "身份揭晓。",
                    "reason": "适合表达震惊。",
                }
            ]

    result = main(["--data-root", str(data_root), "--output-root", str(output_root)], pipeline=FakePipeline())

    assert result == 1
    assert not (output_root / "series_a_ep01" / "highlight_recognition.json").exists()
    assert (output_root / "series_a_ep02" / "highlight_recognition.json").exists()


def test_batch_main_writes_failure_diagnostics_with_raw_llm_response(tmp_path: Path) -> None:
    from pipelines.client import LlmResponseError
    from scripts.run_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")

    class FakePipeline:
        last_llm_call = {
            "status": "failed",
            "elapsed_sec": 0.42,
            "error_type": "LlmResponseError",
            "error": "LLM response is not valid JSON",
            "usage": {"total_tokens": 18},
        }

        def run(self, **kwargs: object) -> list[dict[str, object]]:
            raise LlmResponseError("LLM response is not valid JSON", raw_response_text="不是 JSON")

    result = main(["--data-root", str(data_root), "--output-root", str(output_root)], pipeline=FakePipeline())

    failure_path = output_root / "series_a_ep01" / "llm_failure.json"
    payload = json.loads(failure_path.read_text(encoding="utf-8"))
    assert result == 1
    assert payload["video_id"] == "series_a_ep01"
    assert payload["error_type"] == "LlmResponseError"
    assert payload["error"] == "LLM response is not valid JSON"
    assert payload["raw_response_text"] == "不是 JSON"
    assert payload["danmaku_count"] == 2
    assert payload["llm_call"]["status"] == "failed"
    assert payload["llm_call"]["elapsed_sec"] == 0.42
    assert payload["llm_call"]["usage"]["total_tokens"] == 18

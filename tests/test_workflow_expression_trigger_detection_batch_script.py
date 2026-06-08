from __future__ import annotations

import json
from pathlib import Path
import subprocess
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


def test_workflow_batch_main_writes_clean_asset_and_debug_outputs(tmp_path: Path) -> None:
    from scripts.expression_trigger.run_workflow_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")

    class FakeResult:
        def __init__(self, *, video_id: str, llm_calls: dict[str, object]) -> None:
            self.plot_candidates = [
                {
                    "candidate_id": f"plot_{video_id}_001",
                    "source_branch": "plot_beat",
                    "candidate_type": "payback",
                    "start_time": 5.0,
                    "end_time": 12.0,
                    "trigger_time": 8.0,
                    "summary": "女主反击。",
                }
            ]
            self.punchline_candidates = []
            self.expression_candidates = list(self.plot_candidates)
            self.triggerability_decisions = [
                {
                    "candidate_id": f"plot_{video_id}_001",
                    "decision": "keep",
                    "expression_type": "爽点",
                    "importance_score": 0.91,
                    "start_time": 6.0,
                    "end_time": 9.0,
                    "trigger_time": 8.2,
                    "reason": "适合表达爽感。",
                    "rank_reason": "本集强爽点。",
                }
            ]
            self.candidate_decisions = list(self.triggerability_decisions)
            self.expression_triggers = [
                {
                    "trigger_id": f"et_{video_id}_001",
                    "video_id": video_id,
                    "candidate_id": f"plot_{video_id}_001",
                    "source_branch": "plot_beat",
                    "candidate_type": "payback",
                    "start_time": 6.0,
                    "end_time": 9.0,
                    "trigger_time": 8.2,
                    "expression_type": "爽点",
                    "importance_score": 0.91,
                    "summary": "女主反击。",
                    "reason": "适合表达爽感。",
                }
            ]
            self.resonance_cues = []
            self.llm_calls = llm_calls

    class FakePipeline:
        last_llm_call = {
            "plot_branch": {"status": "success", "usage": {"total_tokens": 10}},
            "punchline_branch": {"status": "success", "usage": {"total_tokens": 11}},
            "triggerability": {"status": "success", "usage": {"total_tokens": 20}},
        }

        def run(
            self,
            *,
            video_id: str,
            video_file_path: Path,
            subtitle_file_path: Path,
            metadata: dict[str, object],
        ) -> WorkflowExpressionTriggerResult:
            self.call = {
                "video_id": video_id,
                "video_file_path": video_file_path,
                "subtitle_file_path": subtitle_file_path,
                "metadata": metadata,
            }
            result = FakeResult(video_id=video_id, llm_calls=self.last_llm_call)
            self.last_result = result
            return result

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

    asset_path = output_root / "series_a_ep01" / "expression_triggers.json"
    debug_path = output_root / "series_a_ep01" / "expression_triggers.debug.json"
    payload = json.loads(asset_path.read_text(encoding="utf-8"))
    debug_payload = json.loads(debug_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["video_id"] == "series_a_ep01"
    assert payload["series_id"] == "series_a"
    assert set(payload) == {"video_id", "series_id", "created_at", "expression_triggers"}
    assert payload["expression_triggers"][0]["expression_type"] == "爽点"
    assert payload["expression_triggers"][0] == {
        "trigger_id": "et_series_a_ep01_001",
        "start_time": 6.0,
        "end_time": 9.0,
        "trigger_time": 8.2,
        "expression_type": "爽点",
        "importance_score": 0.91,
        "summary": "女主反击。",
        "reason": "适合表达爽感。",
    }
    assert debug_payload["video_id"] == "series_a_ep01"
    assert debug_payload["series_id"] == "series_a"
    assert debug_payload["pipeline_type"] == "dual_branch_expression_trigger"
    assert debug_payload["plot_candidates"][0]["candidate_id"] == "plot_series_a_ep01_001"
    assert debug_payload["punchline_candidates"] == []
    assert debug_payload["triggerability_decisions"][0]["importance_score"] == 0.91
    assert debug_payload["expression_candidates"][0]["candidate_id"] == "plot_series_a_ep01_001"
    assert debug_payload["candidate_decisions"][0]["decision"] == "keep"
    assert debug_payload["expression_triggers"][0]["candidate_id"] == "plot_series_a_ep01_001"
    assert debug_payload["resonance_cues"] == []
    assert debug_payload["llm_call"]["plot_branch"]["usage"]["total_tokens"] == 10
    assert debug_payload["llm_call"]["triggerability"]["usage"]["total_tokens"] == 20
    assert not (output_root / "series_a_ep01" / "highlight_recognition.json").exists()
    assert fake_pipeline.call["video_file_path"] == data_root / "series_a" / "ep01" / "video.mp4"
    assert fake_pipeline.call["metadata"]["title"] == "series_a ep01"


def test_workflow_batch_parser_defaults_to_dual_branch() -> None:
    from scripts.expression_trigger.run_workflow_batch import build_parser

    args = build_parser().parse_args([])

    assert args.pipeline == "dual_branch"


def test_expression_trigger_to_asset_item_supports_legacy_cue_time() -> None:
    from scripts.expression_trigger.run_workflow_batch import expression_trigger_to_asset_item

    item = expression_trigger_to_asset_item(
        {
            "trigger_id": "et_demo_ep01_001",
            "start_time": 6.0,
            "end_time": 9.0,
            "cue_time": 8.0,
            "primary_expression": "爽点",
            "interaction_mode": "single_tap",
            "intensity": 0.8,
            "confidence": 0.9,
            "summary": "女主反击。",
            "reason": "适合表达爽感。",
        },
        resonance_cues=[
            {
                "source_trigger_id": "et_demo_ep01_001",
                "ui_trigger_time": 8.5,
            }
        ],
    )

    assert item["cue_time"] == 8.0
    assert item["ui_trigger_time"] == 8.5
    assert "trigger_time" not in item


def test_new_workflow_batch_script_exports_main() -> None:
    from scripts.expression_trigger.run_workflow_batch import main

    assert callable(main)


def test_new_workflow_batch_script_runs_when_executed_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/expression_trigger/run_workflow_batch.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "workflow Expression Trigger Detection" in result.stdout


def test_new_workflow_algorithm_script_runs_when_executed_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/expression_trigger/run_workflow_batch.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "workflow Expression Trigger Detection" in result.stdout


def test_workflow_batch_main_accepts_exact_video_ids(tmp_path: Path) -> None:
    from pipelines.expression_trigger.workflow import WorkflowExpressionTriggerResult
    from scripts.expression_trigger.run_workflow_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_episode(data_root, series_id="series_a", episode_id="ep02")

    class FakePipeline:
        last_llm_call: dict[str, object] = {}

        def __init__(self) -> None:
            self.video_ids: list[str] = []

        def run(self, **kwargs: object) -> WorkflowExpressionTriggerResult:
            self.video_ids.append(str(kwargs["video_id"]))
            return WorkflowExpressionTriggerResult(
                expression_candidates=[],
                candidate_decisions=[],
                expression_triggers=[],
                resonance_cues=[],
                llm_calls={},
            )

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


def test_build_pipeline_passes_filter_sampling_options_to_legacy_pipeline(monkeypatch) -> None:
    import scripts.expression_trigger.run_workflow_batch as batch

    captured: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(batch, "build_llm_client", lambda *, env_path: "fake-client")
    monkeypatch.setattr(
        "pipelines.expression_trigger.workflow.WorkflowExpressionTriggerPipeline",
        FakePipeline,
    )

    pipeline = batch.build_pipeline(
        pipeline_type="legacy",
        env_path=Path(".env.test"),
        sample_interval_sec=10.0,
        max_frames=30,
        frame_max_height=512,
        visual_candidate_window_sec=20.0,
        visual_window_sample_interval_sec=0.5,
        visual_window_max_frames=60,
        filter_frame_interval_sec=2.0,
        filter_candidate_context_sec=3.0,
        filter_max_frames=80,
        final_same_expression_gap_sec=25.0,
        final_min_intensity=0.61,
        final_min_confidence=0.73,
        final_max_triggers=5,
        candidate_max_output_tokens=111,
        filter_max_output_tokens=222,
    )

    assert isinstance(pipeline, FakePipeline)
    assert captured["llm_client"] == "fake-client"
    assert callable(captured["progress_callback"])
    assert captured["visual_candidate_window_sec"] == 20.0
    assert captured["visual_window_sample_interval_sec"] == 0.5
    assert captured["visual_window_max_frames"] == 60
    assert captured["filter_frame_interval_sec"] == 2.0
    assert captured["filter_candidate_context_sec"] == 3.0
    assert captured["filter_max_frames"] == 80
    assert captured["final_same_expression_gap_sec"] == 25.0
    assert captured["final_min_intensity"] == 0.61
    assert captured["final_min_confidence"] == 0.73
    assert captured["final_max_triggers"] == 5


def test_build_pipeline_builds_dual_branch_pipeline(monkeypatch) -> None:
    import scripts.expression_trigger.run_workflow_batch as batch

    captured: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(batch, "build_llm_client", lambda *, env_path: "fake-client")
    monkeypatch.setattr(
        "pipelines.expression_trigger.dual_branch_workflow.DualBranchExpressionTriggerPipeline",
        FakePipeline,
    )

    pipeline = batch.build_pipeline(
        pipeline_type="dual_branch",
        env_path=Path(".env.test"),
        sample_interval_sec=10.0,
        max_frames=30,
        frame_max_height=512,
        visual_candidate_window_sec=20.0,
        visual_window_sample_interval_sec=0.5,
        visual_window_max_frames=60,
        filter_frame_interval_sec=2.0,
        filter_candidate_context_sec=3.0,
        filter_max_frames=80,
        final_same_expression_gap_sec=25.0,
        final_min_intensity=0.61,
        final_min_confidence=0.73,
        final_max_triggers=5,
        candidate_max_output_tokens=111,
        filter_max_output_tokens=222,
    )

    assert isinstance(pipeline, FakePipeline)
    assert captured["llm_client"] == "fake-client"
    assert captured["sample_interval_sec"] == 10.0
    assert captured["max_frames"] == 30
    assert captured["frame_max_height"] == 512
    assert captured["visual_candidate_window_sec"] == 20.0
    assert captured["visual_window_sample_interval_sec"] == 0.5
    assert captured["visual_window_max_frames"] == 60
    assert captured["top_k"] == 5
    assert captured["min_gap_seconds"] == 25.0
    assert captured["branch_max_output_tokens"] == 111
    assert captured["judge_max_output_tokens"] == 222
    assert callable(captured["progress_callback"])


def test_print_workflow_progress_accepts_dual_branch_visual_window_fields(capsys) -> None:
    from scripts.expression_trigger.run_workflow_batch import print_workflow_progress

    print_workflow_progress(
        "prepared",
        {
            "video_id": "beiwang_ep01",
            "duration_sec": 301.141,
            "subtitle_segment_count": 79,
            "visual_candidate_window_count": 4,
            "visual_candidate_windows": [
                {"start_time": 20.0, "end_time": 30.0, "reason": "low_dialogue_density"},
            ],
            "candidate_frame_count": 67,
            "sample_interval_sec": 10.0,
            "visual_candidate_window_sec": 10.0,
            "visual_window_sample_interval_sec": 1.0,
        },
    )

    captured = capsys.readouterr()

    assert "visual_windows=4" in captured.out
    assert "candidate_frames=67" in captured.out
    assert "[beiwang_ep01] visual_window[01]: 20.000-30.000 reason=low_dialogue_density" in captured.out


def test_print_workflow_progress_formats_key_events(capsys) -> None:
    from scripts.expression_trigger.run_workflow_batch import print_workflow_progress

    print_workflow_progress(
        "preprocess_subtitles_loaded",
        {
            "video_id": "beiwang_ep01",
            "subtitle_segment_count": 318,
            "subtitle_duration_sec": 610.2,
        },
    )
    print_workflow_progress(
        "preprocess_duration_probed",
        {
            "video_id": "beiwang_ep01",
            "subtitle_duration_sec": 610.2,
            "video_duration_sec": 612.4,
            "duration_sec": 612.4,
        },
    )
    print_workflow_progress(
        "preprocess_visual_windows_start",
        {
            "video_id": "beiwang_ep01",
            "duration_sec": 612.4,
            "subtitle_segment_count": 318,
            "visual_candidate_window_sec": 20.0,
        },
    )
    print_workflow_progress(
        "preprocess_visual_windows_done",
        {
            "video_id": "beiwang_ep01",
            "visual_window_count": 12,
            "elapsed_sec": 0.03,
        },
    )
    print_workflow_progress(
        "preprocess_candidate_frames_built",
        {
            "video_id": "beiwang_ep01",
            "candidate_frame_count": 142,
            "sample_interval_sec": 10.0,
            "visual_window_sample_interval_sec": 1.0,
        },
    )
    print_workflow_progress(
        "prepared",
        {
            "video_id": "beiwang_ep01",
            "duration_sec": 610.2,
            "subtitle_segment_count": 318,
            "visual_window_count": 12,
            "visual_candidate_windows": [
                {"start_time": 0.0, "end_time": 10.0, "reason": "low_dialogue_density"},
                {"start_time": 40.0, "end_time": 50.0, "reason": "low_dialogue_density"},
            ],
            "candidate_frame_count": 142,
            "sample_interval_sec": 10.0,
            "visual_candidate_window_sec": 20.0,
            "visual_window_sample_interval_sec": 1.0,
        },
    )
    print_workflow_progress(
        "candidate_generation_done",
        {
            "video_id": "beiwang_ep01",
            "candidate_count": 6,
            "elapsed_sec": 28.4,
            "total_tokens": 1820,
        },
    )

    captured = capsys.readouterr()
    assert "[beiwang_ep01] preprocess_subtitles_loaded:" in captured.out
    assert "subtitles=318" in captured.out
    assert "subtitle_duration=610.2s" in captured.out
    assert "[beiwang_ep01] preprocess_duration_probed:" in captured.out
    assert "video_duration=612.4s" in captured.out
    assert "duration=612.4s" in captured.out
    assert "[beiwang_ep01] preprocess_visual_windows_start:" in captured.out
    assert "visual_window_sec=20.0s" in captured.out
    assert "[beiwang_ep01] preprocess_visual_windows_done:" in captured.out
    assert "elapsed=0.03s" in captured.out
    assert "[beiwang_ep01] preprocess_candidate_frames_built:" in captured.out
    assert "[beiwang_ep01] prepared:" in captured.out
    assert "visual_windows=12" in captured.out
    assert "candidate_frames=142" in captured.out
    assert "visual_window_sec=20.0s" in captured.out
    assert "[beiwang_ep01] visual_window[01]: 0.000-10.000 reason=low_dialogue_density" in captured.out
    assert "[beiwang_ep01] visual_window[02]: 40.000-50.000 reason=low_dialogue_density" in captured.out
    assert "[beiwang_ep01] candidate_generation_done:" in captured.out
    assert "candidates=6" in captured.out
    assert "elapsed=28.4s" in captured.out

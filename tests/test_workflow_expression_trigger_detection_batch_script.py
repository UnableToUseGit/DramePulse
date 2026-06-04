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


def test_workflow_batch_main_writes_candidates_and_review_tool_outputs(tmp_path: Path) -> None:
    from pipelines.workflow_expression_trigger_detection import WorkflowExpressionTriggerResult
    from scripts.run_workflow_expression_trigger_detection_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")

    class FakePipeline:
        last_result: WorkflowExpressionTriggerResult | None = None
        last_llm_call = {
            "candidate_generation": {"status": "success", "usage": {"total_tokens": 10}},
            "candidate_filtering": {"status": "success", "usage": {"total_tokens": 20}},
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
            result = WorkflowExpressionTriggerResult(
                expression_candidates=[
                    {
                        "candidate_id": f"cand_{video_id}_001",
                        "video_id": video_id,
                        "start_time": 5.0,
                        "end_time": 12.0,
                        "primary_expression": "爽点",
                        "summary": "女主反击。",
                        "candidate_reason": "可能是压抑后的反击。",
                        "evidence_sources": ["subtitle", "frame"],
                    }
                ],
                candidate_decisions=[
                    {
                        "candidate_id": f"cand_{video_id}_001",
                        "decision": "keep",
                        "primary_expression": "爽点",
                        "role_in_arc": "payoff",
                        "payoff_time": 8.0,
                        "payoff_reason": "反击已经落地。",
                        "decision_reason": "这是清晰反击点。",
                    }
                ],
                expression_triggers=[
                    {
                        "trigger_id": f"et_{video_id}_001",
                        "video_id": video_id,
                        "start_time": 6.0,
                        "end_time": 9.0,
                        "payoff_time": 8.0,
                        "source_type": "plot",
                        "primary_expression": "爽点",
                        "candidate_id": f"cand_{video_id}_001",
                        "decision": "keep",
                        "role_in_arc": "payoff",
                        "interaction_mode": "single_tap",
                        "intensity": 0.8,
                        "confidence": 0.9,
                        "summary": "女主反击。",
                        "setup": "女主此前被压制。",
                        "turning_point": "女主当前反击。",
                        "expression_release": "压抑释放形成爽感。",
                        "reason": "适合表达爽感。",
                    }
                ],
                resonance_cues=[
                    {
                        "cue_id": f"res_{video_id}_001",
                        "video_id": video_id,
                        "source_trigger_id": f"et_{video_id}_001",
                        "ui_trigger_time": 8.5,
                        "duration_sec": 6.0,
                        "emotion_type": "爽点",
                        "label": "爽到了",
                        "icon": "flame",
                        "feedback_text": "你也爽到了",
                        "base_count": 72800,
                        "count_text": "7.3万",
                        "priority": 1,
                    }
                ],
                llm_calls=self.last_llm_call,
            )
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

    output_path = output_root / "series_a_ep01" / "highlight_recognition.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["video_id"] == "series_a_ep01"
    assert payload["expression_candidates"][0]["candidate_id"] == "cand_series_a_ep01_001"
    assert payload["candidate_decisions"][0]["decision"] == "keep"
    assert payload["expression_triggers"][0]["primary_expression"] == "爽点"
    assert payload["expression_triggers"][0]["candidate_id"] == "cand_series_a_ep01_001"
    assert payload["resonance_cues"][0]["emotion_type"] == "爽点"
    assert payload["resonance_cues"][0]["ui_trigger_time"] == 8.5
    assert payload["highlight_assets"][0]["emotion"] == "爽点"
    assert payload["llm_call"]["candidate_generation"]["usage"]["total_tokens"] == 10
    assert payload["llm_call"]["candidate_filtering"]["usage"]["total_tokens"] == 20
    assert fake_pipeline.call["video_file_path"] == data_root / "series_a" / "ep01" / "video.mp4"
    assert fake_pipeline.call["metadata"]["title"] == "series_a ep01"


def test_new_workflow_batch_script_exports_main() -> None:
    from scripts.run_expression_trigger_workflow_batch import main

    assert callable(main)


def test_workflow_batch_main_accepts_exact_video_ids(tmp_path: Path) -> None:
    from pipelines.workflow_expression_trigger_detection import WorkflowExpressionTriggerResult
    from scripts.run_workflow_expression_trigger_detection_batch import main

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


def test_build_pipeline_passes_filter_sampling_options(monkeypatch) -> None:
    import scripts.run_workflow_expression_trigger_detection_batch as batch

    captured: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(batch, "build_llm_client", lambda *, env_path: "fake-client")
    monkeypatch.setattr(
        "pipelines.workflow_expression_trigger_detection.WorkflowExpressionTriggerPipeline",
        FakePipeline,
    )

    pipeline = batch.build_pipeline(
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


def test_print_workflow_progress_formats_key_events(capsys) -> None:
    from scripts.run_workflow_expression_trigger_detection_batch import print_workflow_progress

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

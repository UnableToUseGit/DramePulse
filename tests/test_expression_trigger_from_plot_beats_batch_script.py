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


def make_plot_beats(plot_beat_root: Path, *, video_id: str, series_id: str) -> None:
    output_dir = plot_beat_root / video_id
    output_dir.mkdir(parents=True)
    (output_dir / "plot_beats.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "series_id": series_id,
                "created_at": "2026-06-07T00:00:00Z",
                "chapter_plot_beats": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_from_plot_beats_batch_writes_clean_asset_and_debug_output(tmp_path: Path) -> None:
    from scripts.algorithm.expression_trigger.run_from_plot_beats_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    plot_beat_root = tmp_path / "plot_beat"
    output_root = tmp_path / "expression_trigger"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_plot_beats(plot_beat_root, video_id="series_a_ep01", series_id="series_a")

    class FakeResult:
        video_id = "series_a_ep01"
        series_id = "series_a"
        created_at = "2026-06-07T00:00:00Z"
        plot_candidates = [
            {
                "candidate_id": "pb_ch_series_a_ep01_001_001",
                "source_branch": "plot_beat",
                "candidate_type": "payback",
                "start_time": 5.0,
                "end_time": 8.0,
                "summary": "女主反击。",
            }
        ]
        triggerability_decisions = [
            {
                "candidate_id": "pb_ch_series_a_ep01_001_001",
                "decision": "keep",
                "expression_type": "爽点",
                "importance_score": 0.91,
                "start_time": 5.0,
                "end_time": 8.0,
                "trigger_time": 7.8,
                "reason": "反击完成。",
                "rank_reason": "强爽点。",
            }
        ]
        expression_triggers = [
            {
                "trigger_id": "et_series_a_ep01_001",
                "video_id": "series_a_ep01",
                "candidate_id": "pb_ch_series_a_ep01_001_001",
                "source_branch": "plot_beat",
                "candidate_type": "payback",
                "start_time": 5.0,
                "end_time": 8.0,
                "trigger_time": 7.8,
                "expression_type": "爽点",
                "importance_score": 0.91,
                "summary": "女主反击。",
                "reason": "反击完成。",
            }
        ]
        llm_calls = {"triggerability": {"status": "success", "usage": {"total_tokens": 23}}}

    class FakePipeline:
        def run(self, *, plot_beats_path: Path, subtitle_file_path: Path) -> FakeResult:
            self.call = {"plot_beats_path": plot_beats_path, "subtitle_file_path": subtitle_file_path}
            return FakeResult()

    fake_pipeline = FakePipeline()
    result = main(
        [
            "--data-root",
            str(data_root),
            "--plot-beat-root",
            str(plot_beat_root),
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
    assert set(payload) == {"video_id", "series_id", "created_at", "expression_triggers"}
    assert payload["video_id"] == "series_a_ep01"
    assert payload["series_id"] == "series_a"
    assert payload["expression_triggers"][0] == {
        "trigger_id": "et_series_a_ep01_001",
        "start_time": 5.0,
        "end_time": 8.0,
        "trigger_time": 7.8,
        "expression_type": "爽点",
        "importance_score": 0.91,
        "summary": "女主反击。",
        "reason": "反击完成。",
    }
    assert debug_payload["pipeline_type"] == "plot_beat_triggerability"
    assert debug_payload["plot_candidates"][0]["candidate_id"] == "pb_ch_series_a_ep01_001_001"
    assert debug_payload["triggerability_decisions"][0]["decision"] == "keep"
    assert debug_payload["expression_triggers"][0]["candidate_id"] == "pb_ch_series_a_ep01_001_001"
    assert debug_payload["llm_calls"]["triggerability"]["usage"]["total_tokens"] == 23
    assert fake_pipeline.call["plot_beats_path"] == plot_beat_root / "series_a_ep01" / "plot_beats.json"
    assert fake_pipeline.call["subtitle_file_path"] == data_root / "series_a" / "ep01" / "video.srt"


def test_from_plot_beats_batch_skips_existing_output(tmp_path: Path, capsys) -> None:
    from scripts.algorithm.expression_trigger.run_from_plot_beats_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    plot_beat_root = tmp_path / "plot_beat"
    output_root = tmp_path / "expression_trigger"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_plot_beats(plot_beat_root, video_id="series_a_ep01", series_id="series_a")
    output_path = output_root / "series_a_ep01" / "expression_triggers.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("{}\n", encoding="utf-8")

    class FailingPipeline:
        def run(self, **kwargs):
            raise AssertionError("should skip existing output")

    result = main(
        [
            "--data-root",
            str(data_root),
            "--plot-beat-root",
            str(plot_beat_root),
            "--output-root",
            str(output_root),
        ],
        pipeline=FailingPipeline(),
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "SKIP series_a_ep01" in captured.out


def test_from_plot_beats_batch_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/algorithm/expression_trigger/run_from_plot_beats_batch.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Expression Trigger from raw Plot Beat outputs" in result.stdout

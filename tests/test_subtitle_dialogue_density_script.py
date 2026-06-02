from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_analyze_subtitle_dialogue_density_builds_dialogue_silent_and_density_windows() -> None:
    from pipelines.utils import SubtitleSegment
    from scripts.analyze_subtitle_dialogue_density import analyze_subtitle_segments

    result = analyze_subtitle_segments(
        video_id="demo_ep01",
        series_id="demo",
        episode_id="ep01",
        segments=[
            SubtitleSegment(start=1.0, end=2.0, text="第一句"),
            SubtitleSegment(start=2.4, end=3.0, text="接着说"),
            SubtitleSegment(start=8.0, end=9.0, text="远处一句"),
        ],
        duration_sec=10.0,
        merge_gap_sec=0.5,
        min_silent_sec=1.0,
        window_sec=5.0,
    )

    assert result["video_id"] == "demo_ep01"
    assert result["duration_sec"] == 10.0
    assert result["subtitle_count"] == 3
    assert result["dialogue_ranges"] == [
        {
            "start_time": 1.0,
            "end_time": 3.0,
            "duration_sec": 2.0,
            "subtitle_count": 2,
            "char_count": 6,
            "covered_seconds": 1.6,
            "coverage_ratio": 0.8,
            "chars_per_second": 3.0,
        },
        {
            "start_time": 8.0,
            "end_time": 9.0,
            "duration_sec": 1.0,
            "subtitle_count": 1,
            "char_count": 4,
            "covered_seconds": 1.0,
            "coverage_ratio": 1.0,
            "chars_per_second": 4.0,
        },
    ]
    assert result["silent_ranges"] == [
        {"start_time": 0.0, "end_time": 1.0, "duration_sec": 1.0},
        {"start_time": 3.0, "end_time": 8.0, "duration_sec": 5.0},
        {"start_time": 9.0, "end_time": 10.0, "duration_sec": 1.0},
    ]
    assert result["density_windows"] == [
        {
            "start_time": 0.0,
            "end_time": 5.0,
            "duration_sec": 5.0,
            "subtitle_count": 2,
            "char_count": 6,
            "covered_seconds": 1.6,
            "coverage_ratio": 0.32,
            "chars_per_second": 1.2,
            "utterances_per_minute": 24.0,
            "density_level": "medium",
        },
        {
            "start_time": 5.0,
            "end_time": 10.0,
            "duration_sec": 5.0,
            "subtitle_count": 1,
            "char_count": 4,
            "covered_seconds": 1.0,
            "coverage_ratio": 0.2,
            "chars_per_second": 0.8,
            "utterances_per_minute": 12.0,
            "density_level": "low",
        },
    ]


def test_main_writes_episode_outputs_and_summary(tmp_path: Path) -> None:
    from scripts.analyze_subtitle_dialogue_density import main

    data_root = tmp_path / "DataForAlgorithm"
    episode_dir = data_root / "series_a" / "ep01"
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.srt").write_text(
        "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:02,000",
                "第一句",
                "",
                "2",
                "00:00:08,000 --> 00:00:09,000",
                "第二句",
                "",
            ]
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "output"

    result = main(
        [
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
            "--window-sec",
            "5",
        ]
    )

    episode_output = output_root / "series_a_ep01" / "subtitle_dialogue_density.json"
    summary_output = output_root / "summary.json"
    payload = json.loads(episode_output.read_text(encoding="utf-8"))
    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["video_id"] == "series_a_ep01"
    assert len(payload["silent_ranges"]) >= 1
    assert summary["episode_count"] == 1
    assert summary["total_subtitle_count"] == 2

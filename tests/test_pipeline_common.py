from __future__ import annotations

from pathlib import Path

from pipelines.common.sampling import build_sample_timestamps
from pipelines.common.subtitles import SubtitleSegment, format_subtitle_timeline, load_subtitle_segments, parse_srt


def test_common_subtitles_parse_srt_and_format_timeline(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "demo.srt"
    subtitle_path.write_text("1\n00:00:01,000 --> 00:00:02,500\n你好\n", encoding="utf-8")

    assert parse_srt(subtitle_path.read_text(encoding="utf-8")) == [SubtitleSegment(start=1.0, end=2.5, text="你好")]
    assert load_subtitle_segments(subtitle_path) == [SubtitleSegment(start=1.0, end=2.5, text="你好")]
    assert format_subtitle_timeline([SubtitleSegment(start=1.0, end=2.5, text="你好")]) == (
        "[SUBTITLE_TIMELINE]\n[00:01.000 - 00:02.500] 你好\n[/SUBTITLE_TIMELINE]"
    )


def test_common_sampling_keeps_existing_timestamp_behavior() -> None:
    assert build_sample_timestamps(duration_sec=5.0, sample_interval_sec=2.0, max_frames=None) == [0.0, 2.0, 4.0]
    assert build_sample_timestamps(duration_sec=5.0, sample_interval_sec=1.0, max_frames=3) == [0.0, 2.499, 4.999]

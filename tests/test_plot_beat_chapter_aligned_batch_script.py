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


def make_story_chapters(story_chapter_root: Path, *, video_id: str, series_id: str) -> None:
    output_dir = story_chapter_root / video_id
    output_dir.mkdir(parents=True)
    (output_dir / "story_chapters.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "series_id": series_id,
                "created_at": "2026-06-07T00:00:00Z",
                "story_chapters": [
                    {
                        "chapter_id": f"ch_{video_id}_001",
                        "start_time": 0.0,
                        "end_time": 20.0,
                        "title": "测试章节",
                        "summary": "测试章节摘要。",
                        "reason": "测试。",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_plot_beat_chapter_aligned_batch_writes_output(tmp_path: Path) -> None:
    from scripts.plot_beat.run_chapter_aligned_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    story_chapter_root = tmp_path / "story_chapter"
    output_root = tmp_path / "plot_beat"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_story_chapters(story_chapter_root, video_id="series_a_ep01", series_id="series_a")

    class FakeResult:
        video_id = "series_a_ep01"
        series_id = "series_a"
        created_at = "2026-06-07T00:00:00Z"
        chapter_plot_beats = [
            {
                "video_id": "series_a_ep01",
                "series_id": "series_a",
                "created_at": "2026-06-07T00:00:00Z",
                "chapter_id": "ch_series_a_ep01_001",
                "plot_beats": [
                    {
                        "beat_id": "pb_ch_series_a_ep01_001_001",
                        "beat_type": "reversal",
                        "start_time": 5.0,
                        "end_time": 8.0,
                        "summary": "剧情反转。",
                        "reason": "状态变化。",
                    }
                ],
            }
        ]
        llm_calls = {"ch_series_a_ep01_001": {"status": "success"}}

    class FakePipeline:
        def run(
            self,
            *,
            video_file_path: Path,
            subtitle_file_path: Path,
            story_chapters_path: Path,
        ) -> FakeResult:
            self.call = {
                "video_file_path": video_file_path,
                "subtitle_file_path": subtitle_file_path,
                "story_chapters_path": story_chapters_path,
            }
            return FakeResult()

    fake_pipeline = FakePipeline()
    result = main(
        [
            "--data-root",
            str(data_root),
            "--story-chapter-root",
            str(story_chapter_root),
            "--output-root",
            str(output_root),
        ],
        pipeline=fake_pipeline,
    )

    output_path = output_root / "series_a_ep01" / "plot_beats.json"
    debug_path = output_root / "series_a_ep01" / "plot_beats.debug.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    debug_payload = json.loads(debug_path.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["video_id"] == "series_a_ep01"
    assert payload["series_id"] == "series_a"
    assert payload["chapter_plot_beats"][0]["plot_beats"][0]["beat_type"] == "reversal"
    assert "llm_calls" not in payload
    assert debug_payload["video_id"] == "series_a_ep01"
    assert debug_payload["series_id"] == "series_a"
    assert debug_payload["created_at"] == "2026-06-07T00:00:00Z"
    assert debug_payload["llm_calls"]["ch_series_a_ep01_001"]["status"] == "success"
    assert fake_pipeline.call["video_file_path"] == data_root / "series_a" / "ep01" / "video.mp4"
    assert fake_pipeline.call["subtitle_file_path"] == data_root / "series_a" / "ep01" / "video.srt"
    assert fake_pipeline.call["story_chapters_path"] == story_chapter_root / "series_a_ep01" / "story_chapters.json"


def test_plot_beat_chapter_aligned_batch_skips_existing_output(tmp_path: Path, capsys) -> None:
    from scripts.plot_beat.run_chapter_aligned_batch import main

    data_root = tmp_path / "DataForAlgorithm"
    story_chapter_root = tmp_path / "story_chapter"
    output_root = tmp_path / "plot_beat"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    make_story_chapters(story_chapter_root, video_id="series_a_ep01", series_id="series_a")
    output_path = output_root / "series_a_ep01" / "plot_beats.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("{}\n", encoding="utf-8")

    class FailingPipeline:
        def run(self, **kwargs):
            raise AssertionError("should skip existing output")

    result = main(
        [
            "--data-root",
            str(data_root),
            "--story-chapter-root",
            str(story_chapter_root),
            "--output-root",
            str(output_root),
        ],
        pipeline=FailingPipeline(),
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "SKIP series_a_ep01" in captured.out


def test_plot_beat_chapter_aligned_batch_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/plot_beat/run_chapter_aligned_batch.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "chapter-aligned Plot Beat" in result.stdout


def test_print_plot_beat_progress_formats_key_events(capsys) -> None:
    from scripts.plot_beat.run_chapter_aligned_batch import print_plot_beat_progress

    print_plot_beat_progress(
        "prepared",
        {
            "video_id": "beiwang_ep01",
            "series_id": "beiwang",
            "chapter_count": 4,
            "subtitle_segment_count": 79,
            "duration_sec": 301.1,
        },
    )
    print_plot_beat_progress(
        "chapter_start",
        {
            "video_id": "beiwang_ep01",
            "chapter_id": "ch_beiwang_ep01_001",
            "chapter_index": 1,
            "chapter_count": 4,
            "start_time": 0.0,
            "end_time": 83.5,
            "title": "讨薪成功",
        },
    )
    print_plot_beat_progress(
        "chapter_frames_extracted",
        {
            "video_id": "beiwang_ep01",
            "chapter_id": "ch_beiwang_ep01_001",
            "requested_frame_count": 60,
            "extracted_frame_count": 60,
            "image_count": 60,
        },
    )
    print_plot_beat_progress(
        "chapter_llm_done",
        {
            "video_id": "beiwang_ep01",
            "chapter_id": "ch_beiwang_ep01_001",
            "beat_count": 3,
            "elapsed_sec": 12.345,
            "total_tokens": 1234,
        },
    )
    print_plot_beat_progress("completed", {"video_id": "beiwang_ep01", "chapter_count": 4, "beat_count": 9})

    captured = capsys.readouterr()

    assert "[beiwang_ep01] prepared: chapters=4 subtitles=79 duration=301.1s" in captured.out
    assert "[beiwang_ep01] chapter_start [1/4] ch_beiwang_ep01_001 0.0-83.5s title=讨薪成功" in captured.out
    assert "[beiwang_ep01] chapter_frames_extracted ch_beiwang_ep01_001: requested=60 extracted=60 images=60" in captured.out
    assert "[beiwang_ep01] chapter_llm_done ch_beiwang_ep01_001: beats=3 elapsed=12.345s tokens=1234" in captured.out
    assert "[beiwang_ep01] completed: chapters=4 beats=9" in captured.out

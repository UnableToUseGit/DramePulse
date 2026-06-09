from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelines.common.media import FrameExtractionResult
from pipelines.plot_beat.chapter_aligned import (
    ChapterAlignedPlotBeatPipeline,
    build_chapter_frame_timestamps,
    build_chapter_plot_beat_user_prompt,
    parse_chapter_plot_beat_result,
)


class FakeLlmClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.last_call_diagnostics: dict[str, Any] = {}

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 2400,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_paths": image_paths or [],
                "frame_timestamps_seconds": frame_timestamps_seconds or [],
                "max_tokens": max_tokens,
            }
        )
        self.last_call_diagnostics = {"status": "success", "request_index": len(self.calls)}
        return self.responses.pop(0)


def write_srt(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:03,000",
                "大家去找工头要钱",
                "",
                "2",
                "00:00:10,000 --> 00:00:12,000",
                "钱我已经凑齐了",
                "",
                "3",
                "00:00:40,000 --> 00:00:42,000",
                "年三十我一定回家",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_story_chapters(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "video_id": "beiwang_ep01",
                "series_id": "beiwang",
                "created_at": "2026-06-07T00:00:00Z",
                "story_chapters": [
                    {
                        "chapter_id": "ch_beiwang_ep01_001",
                        "start_time": 0.0,
                        "end_time": 20.0,
                        "title": "讨薪成功",
                        "summary": "工人找工头讨薪，工头说明已凑齐工资。",
                        "reason": "讨薪事件完成。",
                    },
                    {
                        "chapter_id": "ch_beiwang_ep01_002",
                        "start_time": 35.0,
                        "end_time": 50.0,
                        "title": "决定回家",
                        "summary": "儿子告诉母亲年三十一定回家。",
                        "reason": "返乡目标明确。",
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_chapter_frame_timestamps_samples_one_second_and_caps_to_sixty() -> None:
    short = build_chapter_frame_timestamps(chapter_start_time=10.0, chapter_end_time=14.2)
    long = build_chapter_frame_timestamps(chapter_start_time=0.0, chapter_end_time=120.0)

    assert short == [10.0, 11.0, 12.0, 13.0, 14.0]
    assert len(long) == 60
    assert long[0] == 0.0
    assert long[-1] == 119.0
    assert all(timestamp == round(timestamp, 1) for timestamp in long)


def test_build_chapter_plot_beat_prompt_uses_full_subtitles_and_current_chapter() -> None:
    prompt = build_chapter_plot_beat_user_prompt(
        video_id="beiwang_ep01",
        series_id="beiwang",
        video_duration_seconds=80.0,
        full_subtitles_timeline="[1.0-3.0] 大家去找工头要钱\n[40.0-42.0] 年三十我一定回家",
        chapter={
            "chapter_id": "ch_beiwang_ep01_002",
            "start_time": 35.0,
            "end_time": 50.0,
            "title": "决定回家",
            "summary": "儿子告诉母亲年三十一定回家。",
        },
    )

    assert "FULL_SUBTITLES" in prompt
    assert "[1.0-3.0] 大家去找工头要钱" in prompt
    assert "CURRENT_CHAPTER" in prompt
    assert "ch_beiwang_ep01_002" in prompt
    assert "只输出当前 chapter 范围内" in prompt
    assert "atomic story-state change" in prompt
    assert "conflict_start: A new central conflict is introduced or breaks out." in prompt
    assert "relationship_advance: A relationship becomes closer, clearer, or enters a new stage." in prompt
    assert "trigger_time" not in prompt


def test_parse_chapter_plot_beat_result_keeps_model_outputs_without_semantic_filtering() -> None:
    parsed = parse_chapter_plot_beat_result(
        {
            "plot_beats": [
                {
                    "beat_type": "reversal",
                    "start_time": 10.0,
                    "end_time": 12.0,
                    "summary": "工头说明钱已凑齐。",
                    "reason": "剧情从讨薪冲突转为工资即将结清。",
                },
                {
                    "beat_type": "reversal",
                    "start_time": 0.0,
                    "end_time": 20.0,
                    "summary": "整段讨薪完成。",
                    "reason": "太宽。",
                },
                {
                    "beat_type": "unknown",
                    "start_time": -1.0,
                    "end_time": 30.0,
                    "summary": "非法类型。",
                    "reason": "非法类型。",
                },
            ]
        },
        video_id="beiwang_ep01",
        series_id="beiwang",
        created_at="2026-06-07T00:00:00Z",
        chapter_id="ch_beiwang_ep01_001",
        chapter_start_time=0.0,
        chapter_end_time=20.0,
    )

    assert parsed == {
        "video_id": "beiwang_ep01",
        "series_id": "beiwang",
        "created_at": "2026-06-07T00:00:00Z",
        "chapter_id": "ch_beiwang_ep01_001",
        "plot_beats": [
            {
                "beat_id": "pb_ch_beiwang_ep01_001_001",
                "beat_type": "reversal",
                "start_time": 10.0,
                "end_time": 12.0,
                "summary": "工头说明钱已凑齐。",
                "reason": "剧情从讨薪冲突转为工资即将结清。",
            },
            {
                "beat_id": "pb_ch_beiwang_ep01_001_002",
                "beat_type": "reversal",
                "start_time": 0.0,
                "end_time": 20.0,
                "summary": "整段讨薪完成。",
                "reason": "太宽。",
            },
            {
                "beat_id": "pb_ch_beiwang_ep01_001_003",
                "beat_type": "unknown",
                "start_time": -1.0,
                "end_time": 30.0,
                "summary": "非法类型。",
                "reason": "非法类型。",
            },
        ],
    }


def test_chapter_aligned_pipeline_calls_llm_once_per_chapter(tmp_path: Path, monkeypatch: Any) -> None:
    from pipelines.plot_beat import chapter_aligned

    subtitle_path = tmp_path / "video.srt"
    video_path = tmp_path / "video.mp4"
    story_chapters_path = tmp_path / "story_chapters.json"
    write_srt(subtitle_path)
    write_story_chapters(story_chapters_path)
    video_path.write_bytes(b"fake video")

    def fake_probe_video_duration_seconds(path: Path) -> float:
        assert path == video_path
        return 80.0

    def fake_extract_frames_at_timestamps(
        *,
        video_path: Path,
        output_dir: Path,
        timestamps_seconds: list[float],
        max_height: int,
    ) -> FrameExtractionResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        for index, _timestamp in enumerate(timestamps_seconds, start=1):
            (output_dir / f"frame_{index:03d}.png").write_bytes(b"fake png")
        return FrameExtractionResult(backend="fake", frame_count=len(timestamps_seconds))

    monkeypatch.setattr(chapter_aligned, "probe_video_duration_seconds", fake_probe_video_duration_seconds)
    monkeypatch.setattr(chapter_aligned, "extract_frames_at_timestamps", fake_extract_frames_at_timestamps)

    llm = FakeLlmClient(
        [
            {
                "plot_beats": [
                    {
                        "beat_type": "reversal",
                        "start_time": 10.0,
                        "end_time": 12.0,
                        "summary": "工头说明钱已凑齐。",
                        "reason": "讨薪冲突转为解决。",
                    }
                ]
            },
            {"plot_beats": []},
        ]
    )

    pipeline = ChapterAlignedPlotBeatPipeline(llm_client=llm)
    result = pipeline.run(
        video_file_path=video_path,
        subtitle_file_path=subtitle_path,
        story_chapters_path=story_chapters_path,
    )

    assert result.video_id == "beiwang_ep01"
    assert result.series_id == "beiwang"
    assert len(result.chapter_plot_beats) == 2
    assert result.chapter_plot_beats[0]["chapter_id"] == "ch_beiwang_ep01_001"
    assert result.chapter_plot_beats[0]["plot_beats"][0]["beat_id"] == "pb_ch_beiwang_ep01_001_001"
    assert len(llm.calls) == 2
    assert "FULL_SUBTITLES" in llm.calls[0]["user_prompt"]
    assert "[1.0-3.0] 大家去找工头要钱" in llm.calls[0]["user_prompt"]
    assert "[1.000-3.000]" not in llm.calls[0]["user_prompt"]
    assert "ch_beiwang_ep01_001" in llm.calls[0]["user_prompt"]
    assert "ch_beiwang_ep01_002" in llm.calls[1]["user_prompt"]
    assert llm.calls[0]["frame_timestamps_seconds"] == build_chapter_frame_timestamps(
        chapter_start_time=0.0,
        chapter_end_time=20.0,
    )

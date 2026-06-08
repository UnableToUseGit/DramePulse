from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FakeLlmClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
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
        self.last_call_diagnostics = {"status": "success", "usage": {"total_tokens": 123}}
        return self.response


def write_srt(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:10,000 --> 00:00:12,000",
                "你终于输了",
                "",
                "2",
                "00:00:20,000 --> 00:00:22,000",
                "我要让你当众道歉",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_plot_beats(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "video_id": "series_a_ep01",
                "series_id": "series_a",
                "created_at": "2026-06-07T00:00:00Z",
                "chapter_plot_beats": [
                    {
                        "chapter_id": "ch_series_a_ep01_001",
                        "plot_beats": [
                            {
                                "beat_id": "pb_ch_series_a_ep01_001_001",
                                "beat_type": "payback",
                                "start_time": 10.0,
                                "end_time": 12.0,
                                "summary": "女主逼反派认输。",
                                "reason": "被压制的一方完成反击。",
                            },
                            {
                                "beat_id": "pb_ch_series_a_ep01_001_002",
                                "beat_type": "conflict_start",
                                "start_time": 20.0,
                                "end_time": 22.0,
                                "summary": "新冲突出现。",
                                "reason": "只是开启冲突。",
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_plot_beat_triggerability_pipeline_selects_expression_triggers(tmp_path: Path) -> None:
    from pipelines.expression_trigger.from_plot_beats import PlotBeatTriggerabilityPipeline

    subtitle_path = tmp_path / "video.srt"
    plot_beats_path = tmp_path / "plot_beats.json"
    write_srt(subtitle_path)
    write_plot_beats(plot_beats_path)

    llm = FakeLlmClient(
        {
            "triggerability_decisions": [
                {
                    "candidate_id": "pb_ch_series_a_ep01_001_001",
                    "expression_type": "爽点",
                    "rubric_scores": {
                        "semantic_fit": 2,
                        "emotional_release": 2,
                        "viewer_impulse": 2,
                        "type_specific": 2,
                    },
                    "disqualifier": "",
                    "reason": "反击完成，适合触发表达。",
                },
                {
                    "candidate_id": "pb_ch_series_a_ep01_001_002",
                    "expression_type": "none",
                    "rubric_scores": {
                        "semantic_fit": 0,
                        "emotional_release": 0,
                        "viewer_impulse": 0,
                        "type_specific": 0,
                    },
                    "disqualifier": "只是冲突开始，没有表达释放。",
                    "reason": "只是冲突开始，没有表达释放。",
                },
            ]
        }
    )

    pipeline = PlotBeatTriggerabilityPipeline(llm_client=llm, top_k=4, min_gap_seconds=30.0)
    result = pipeline.run(plot_beats_path=plot_beats_path, subtitle_file_path=subtitle_path)

    assert result.video_id == "series_a_ep01"
    assert result.series_id == "series_a"
    assert [candidate["candidate_id"] for candidate in result.plot_candidates] == [
        "pb_ch_series_a_ep01_001_001",
        "pb_ch_series_a_ep01_001_002",
    ]
    assert result.plot_candidates[0]["source_beat_id"] == "pb_ch_series_a_ep01_001_001"
    assert result.plot_candidates[0]["chapter_id"] == "ch_series_a_ep01_001"
    assert [decision["decision"] for decision in result.triggerability_decisions] == ["keep", "reject"]
    assert len(result.expression_triggers) == 1
    assert result.expression_triggers[0]["trigger_id"] == "et_series_a_ep01_001"
    assert result.expression_triggers[0]["candidate_id"] == "pb_ch_series_a_ep01_001_001"
    assert result.expression_triggers[0]["start_time"] == 10.0
    assert result.expression_triggers[0]["end_time"] == 12.0
    assert result.expression_triggers[0]["trigger_time"] == 12.0
    assert result.expression_triggers[0]["total_score"] == 8
    assert result.expression_triggers[0]["rubric_scores"]["semantic_fit"] == 2
    assert result.llm_calls["triggerability"]["usage"]["total_tokens"] == 123
    assert result.llm_calls["triggerability"]["parsed_response"] == llm.response
    assert len(llm.calls) == 1
    assert "raw plot beat" in llm.calls[0]["system_prompt"]
    assert "player expression trigger" in llm.calls[0]["user_prompt"]
    assert "[10.0-12.0] 你终于输了" in llm.calls[0]["user_prompt"]
    assert "[10.000-12.000]" not in llm.calls[0]["user_prompt"]
    assert llm.calls[0]["image_paths"] == []
    assert llm.calls[0]["frame_timestamps_seconds"] == []


def test_build_prompt_rejects_setup_only_conflict_starts() -> None:
    from pipelines.expression_trigger.from_plot_beats import build_plot_beat_triggerability_prompt

    prompt = build_plot_beat_triggerability_prompt(
        video_id="series_a_ep01",
        video_duration_seconds=30.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\n[10.0-12.0] 你终于输了\n[/SUBTITLE_TIMELINE]",
        plot_candidates=[
            {
                "candidate_id": "pb_ch_series_a_ep01_001_001",
                "candidate_type": "conflict_start",
                "start_time": 10.0,
                "end_time": 12.0,
                "summary": "新冲突出现。",
            }
        ],
        top_k=4,
        min_gap_seconds=30.0,
    )

    assert "raw plot beat" in prompt
    assert "Setup-only conflict starts" in prompt
    assert "hated antagonist" in prompt
    assert "benevolent repayment" in prompt
    assert "kissing" in prompt
    assert "rubric_scores" in prompt
    assert "Judge every candidate independently" in prompt
    assert "Do not perform top-k selection" in prompt
    assert "Do not output or adjust timing fields" in prompt
    assert "top_k=4" not in prompt
    assert "`start_time`" not in prompt
    assert "`end_time`" not in prompt
    assert "`trigger_time`" not in prompt
    assert "timing_clarity" not in prompt
    assert "泪点" in prompt
    assert "甜点" in prompt

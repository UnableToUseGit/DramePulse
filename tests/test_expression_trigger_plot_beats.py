from pipelines.expression_trigger.plot_beats import (
    build_plot_beat_prompt,
    parse_plot_beat_candidates,
)


def test_parse_plot_beat_candidates_keeps_valid_candidate() -> None:
    raw = {
        "plot_candidates": [
            {
                "candidate_id": "ignored_by_parser",
                "candidate_type": "payback",
                "start_time": 58.0,
                "end_time": 72.0,
                "trigger_time": 67.0,
                "summary": "女主掀桌反击。",
                "setup": "儿子被嫂子刁难。",
                "turning_point": "女主到场掀桌。",
                "payoff": "被欺负的一方夺回主动权。",
                "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
            }
        ]
    }

    candidates = parse_plot_beat_candidates(raw, video_id="jialijiawai_ep02", duration_sec=300.0)

    assert candidates == [
        {
            "candidate_id": "plot_jialijiawai_ep02_001",
            "source_branch": "plot_beat",
            "candidate_type": "payback",
            "start_time": 58.0,
            "end_time": 72.0,
            "trigger_time": 67.0,
            "summary": "女主掀桌反击。",
            "setup": "儿子被嫂子刁难。",
            "turning_point": "女主到场掀桌。",
            "payoff": "被欺负的一方夺回主动权。",
            "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
        }
    ]


def test_parse_plot_beat_candidates_rejects_invalid_type_and_time() -> None:
    raw = {
        "plot_candidates": [
            {"candidate_type": "random", "start_time": 1.0, "end_time": 2.0, "trigger_time": 1.5},
            {"candidate_type": "payback", "start_time": 3.0, "end_time": 2.0, "trigger_time": 2.5},
            {"candidate_type": "payback", "start_time": 1.0, "end_time": 4.0, "trigger_time": 8.0},
        ]
    }

    assert parse_plot_beat_candidates(raw, video_id="demo_ep01", duration_sec=10.0) == []


def test_build_plot_beat_prompt_contains_branch_contract() -> None:
    prompt = build_plot_beat_prompt(
        video_id="demo_ep01",
        video_duration_seconds=120.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\n[1.000-2.000] 你凭啥子\n[/SUBTITLE_TIMELINE]",
        metadata={"series": "demo"},
        frame_timestamps_seconds=[0.0, 10.0],
    )

    assert "Plot Beat Branch" in prompt
    assert "conflict_start" in prompt
    assert "trigger_time" in prompt
    assert "plot_candidates" in prompt

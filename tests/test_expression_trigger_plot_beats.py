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
                "summary": "女主掀桌反击。",
                "reason": "女主从被动受辱转为主动压制对方，剧情权力关系发生变化。",
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
            "summary": "女主掀桌反击。",
            "reason": "女主从被动受辱转为主动压制对方，剧情权力关系发生变化。",
            "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
        }
    ]


def test_parse_plot_beat_candidates_rejects_invalid_type_and_time() -> None:
    raw = {
        "plot_candidates": [
            {"candidate_type": "random", "start_time": 1.0, "end_time": 2.0},
            {"candidate_type": "payback", "start_time": 3.0, "end_time": 2.0},
            {"candidate_type": "payback", "start_time": 1.0, "end_time": 14.0},
        ]
    }

    assert parse_plot_beat_candidates(raw, video_id="demo_ep01", duration_sec=10.0) == []


def test_parse_plot_beat_candidates_rejects_chapter_like_interval() -> None:
    raw = {
        "plot_candidates": [
            {
                "candidate_type": "family_emotional_payoff",
                "start_time": 135.26,
                "end_time": 241.9,
                "summary": "母子通电话。",
                "reason": "整段电话体现亲情。",
                "evidence": ["135.260-241.900 母子通电话"],
            }
        ]
    }

    assert parse_plot_beat_candidates(raw, video_id="beiwang_ep01", duration_sec=301.141) == []


def test_parse_plot_beat_candidates_rejects_multi_sentence_arc() -> None:
    raw = {
        "plot_candidates": [
            {
                "candidate_type": "reversal",
                "start_time": 30.0,
                "end_time": 73.71,
                "summary": "工头主动发工资，欠薪矛盾解决。",
                "reason": "整段讨薪冲突被解决。",
                "evidence": ["30.000-73.710 工头发工资"],
            }
        ]
    }

    assert parse_plot_beat_candidates(raw, video_id="beiwang_ep01", duration_sec=301.141) == []


def test_build_plot_beat_prompt_contains_branch_contract() -> None:
    prompt = build_plot_beat_prompt(
        video_id="demo_ep01",
        video_duration_seconds=120.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\n[1.000-2.000] 你凭啥子\n[/SUBTITLE_TIMELINE]",
        metadata={"series": "demo"},
    )

    assert "short-drama plot beat annotator" in prompt
    assert "expression-trigger" not in prompt
    assert "Expression Trigger" not in prompt
    assert "conflict_start" in prompt
    assert "conflict_start: A new central conflict is introduced or breaks out." in prompt
    assert "family_emotional_payoff: A family-related emotional setup pays off through a specific line or action." in prompt
    assert "trigger_time" not in prompt
    assert "turning_point" not in prompt
    assert "`setup`" not in prompt
    assert "`reason`" in prompt
    assert "atomic story-state change" in prompt
    assert "one shot or one/two adjacent subtitle lines" in prompt
    assert "smallest possible interval" in prompt
    assert "Target 1-8 seconds" in prompt
    assert "15 seconds" in prompt
    assert "Never output a whole phone call" in prompt
    assert "FRAME_TIMESTAMPS_SECONDS" not in prompt
    assert "plot_candidates" in prompt

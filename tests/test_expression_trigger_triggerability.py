from pipelines.expression_trigger.triggerability import (
    build_triggerability_prompt,
    parse_triggerability_decisions,
    select_top_expression_triggers,
)


def test_parse_triggerability_decisions_keeps_valid_decision() -> None:
    candidates = [
        {
            "candidate_id": "plot_demo_ep01_001",
            "source_branch": "plot_beat",
            "candidate_type": "payback",
            "start_time": 10.0,
            "end_time": 20.0,
            "summary": "女主打脸反派。",
        }
    ]
    raw = {
        "triggerability_decisions": [
            {
                "candidate_id": "plot_demo_ep01_001",
                "decision": "keep",
                "expression_type": "爽点",
                "importance_score": 0.91,
                "start_time": 10.0,
                "end_time": 20.0,
                "trigger_time": 18.5,
                "reason": "反击完成，解气明确。",
                "rank_reason": "本集强爽点。",
            }
        ]
    }

    decisions = parse_triggerability_decisions(raw, candidates=candidates)

    assert decisions[0]["decision"] == "keep"
    assert decisions[0]["expression_type"] == "爽点"
    assert decisions[0]["trigger_time"] == 18.5


def test_parse_triggerability_decisions_rejects_unsupported_expression() -> None:
    candidates = [{"candidate_id": "plot_demo_ep01_001", "start_time": 1.0, "end_time": 3.0, "trigger_time": 2.0}]
    raw = {
        "triggerability_decisions": [
            {
                "candidate_id": "plot_demo_ep01_001",
                "decision": "keep",
                "expression_type": "震惊",
                "importance_score": 0.9,
                "start_time": 1.0,
                "end_time": 3.0,
                "trigger_time": 2.0,
                "reason": "突然。",
                "rank_reason": "意外。",
            }
        ]
    }

    assert parse_triggerability_decisions(raw, candidates=candidates)[0]["decision"] == "reject"


def test_parse_triggerability_decisions_adds_missing_rejects() -> None:
    candidates = [
        {"candidate_id": "plot_demo_ep01_001", "start_time": 1.0, "end_time": 3.0, "trigger_time": 2.0},
        {"candidate_id": "plot_demo_ep01_002", "start_time": 4.0, "end_time": 6.0, "trigger_time": 5.0},
    ]

    decisions = parse_triggerability_decisions({"triggerability_decisions": []}, candidates=candidates)

    assert [decision["candidate_id"] for decision in decisions] == ["plot_demo_ep01_001", "plot_demo_ep01_002"]
    assert {decision["decision"] for decision in decisions} == {"reject"}
    assert decisions[0]["reason"] == "missing triggerability decision"


def test_select_top_expression_triggers_applies_score_and_gap() -> None:
    decisions = [
        {
            "candidate_id": "a",
            "decision": "keep",
            "expression_type": "爽点",
            "importance_score": 0.80,
            "start_time": 10.0,
            "end_time": 20.0,
            "trigger_time": 18.0,
            "reason": "弱一点。",
        },
        {
            "candidate_id": "b",
            "decision": "keep",
            "expression_type": "爽点",
            "importance_score": 0.95,
            "start_time": 22.0,
            "end_time": 30.0,
            "trigger_time": 28.0,
            "reason": "同类更强。",
        },
        {
            "candidate_id": "c",
            "decision": "keep",
            "expression_type": "笑点",
            "importance_score": 0.70,
            "start_time": 60.0,
            "end_time": 66.0,
            "trigger_time": 64.0,
            "reason": "笑点。",
        },
    ]

    triggers = select_top_expression_triggers(decisions, video_id="demo_ep01", top_k=4, min_gap_seconds=20.0)

    assert [trigger["candidate_id"] for trigger in triggers] == ["b", "c"]
    assert triggers[0]["trigger_id"] == "et_demo_ep01_001"


def test_build_triggerability_prompt_contains_topk_contract() -> None:
    prompt = build_triggerability_prompt(
        video_id="demo_ep01",
        video_duration_seconds=100.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\n[/SUBTITLE_TIMELINE]",
        candidates=[{"candidate_id": "a", "summary": "x"}],
        top_k=4,
        min_gap_seconds=20.0,
    )

    assert "Triggerability Judge" in prompt
    assert "top_k=4" in prompt
    assert "trigger_time" in prompt
    assert "hated antagonist" in prompt
    assert "benevolent repayment" in prompt
    assert "kissing" in prompt

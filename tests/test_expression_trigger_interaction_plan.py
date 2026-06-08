from pipelines.expression_trigger.interaction_plan import build_expression_interaction_plan


def test_build_expression_interaction_plan_maps_trigger_to_emotional_button() -> None:
    plan = build_expression_interaction_plan(
        [
            {
                "trigger_id": "et_series_a_ep03_001",
                "start_time": 5.0,
                "end_time": 8.0,
                "trigger_time": 7.8,
                "expression_type": "爽点",
                "importance_score": 0.91,
                "summary": "女主反击。",
                "reason": "反击完成。",
            }
        ],
        video_id="series_a_ep03",
        series_id="series_a",
    )

    assert plan == [
        {
            "interaction_id": "ip_series_a_ep03_001",
            "video_id": "series_a_ep03",
            "series_id": "series_a",
            "episode_no": 3,
            "interaction_mode": "emotional_button",
            "trigger_time": 7.8,
            "duration_sec": 5.0,
            "expire_time": 12.8,
            "content": {
                "expression_type": "爽点",
                "source_trigger_id": "et_series_a_ep03_001",
                "source_start_time": 5.0,
                "source_end_time": 8.0,
            },
        }
    ]


def test_build_expression_interaction_plan_uses_stable_ids_and_episode_number() -> None:
    plan = build_expression_interaction_plan(
        [
            {
                "trigger_id": "et_demo_ep01_001",
                "trigger_time": 10.0,
                "expression_type": "泪点",
                "summary": "母亲等孩子回家。",
                "reason": "亲情释放。",
            },
            {
                "trigger_id": "et_demo_ep01_002",
                "trigger_time": 30.0,
                "expression_type": "笑点",
                "summary": "误会反转。",
                "reason": "包袱落地。",
            },
        ],
        video_id="demo_ep01",
        series_id="demo",
    )

    assert [item["interaction_id"] for item in plan] == ["ip_demo_ep01_001", "ip_demo_ep01_002"]
    assert [item["episode_no"] for item in plan] == [1, 1]
    assert [item["interaction_mode"] for item in plan] == ["emotional_button", "emotional_button"]

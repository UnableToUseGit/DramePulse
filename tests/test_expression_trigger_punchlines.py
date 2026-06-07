from pipelines.expression_trigger.punchlines import build_punchline_prompt, parse_punchline_candidates


def test_parse_punchline_candidates_sets_laugh_expression() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 59.83,
                "end_time": 68.15,
                "trigger_time": 64.75,
                "summary": "女主用口水帮领导消毒形成笑点。",
                "setup": "领导夸张担心毒素进脑壳。",
                "punchline": "来嘛，我帮你消毒！",
                "payoff": "夸张担心和女主反制形成喜剧反差。",
                "evidence": ["63.430-64.750 来嘛，我帮你消毒！"],
            }
        ]
    }

    candidates = parse_punchline_candidates(raw, video_id="jialijiawai_ep01", duration_sec=220.0)

    assert candidates[0]["candidate_id"] == "punchline_jialijiawai_ep01_001"
    assert candidates[0]["source_branch"] == "punchline"
    assert candidates[0]["candidate_type"] == "punchline"
    assert candidates[0]["expression_type"] == "笑点"
    assert candidates[0]["trigger_time"] == 64.75


def test_parse_punchline_candidates_rejects_missing_punchline_text() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 1.0,
                "end_time": 4.0,
                "trigger_time": 3.0,
                "summary": "普通剧情",
                "setup": "",
                "punchline": "",
                "payoff": "",
                "evidence": [],
            }
        ]
    }

    assert parse_punchline_candidates(raw, video_id="demo_ep01", duration_sec=10.0) == []


def test_build_punchline_prompt_mentions_non_plot_boundary() -> None:
    prompt = build_punchline_prompt(
        video_id="demo_ep01",
        video_duration_seconds=120.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\n[1.000-2.000] 哈哈\n[/SUBTITLE_TIMELINE]",
        metadata={},
    )

    assert "Punchline Branch" in prompt
    assert "笑点" in prompt
    assert "Do not output plot payback" in prompt

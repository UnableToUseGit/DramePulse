from pipelines.expression_trigger.punchlines import build_punchline_prompt, parse_punchline_candidates


def test_parse_punchline_candidates_sets_laugh_expression() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 59.83,
                "end_time": 68.15,
                "summary": "女主用口水帮领导消毒形成笑点。",
                "punchline_text": "来嘛，我帮你消毒！",
                "reason": "女主把领导对毒素的夸张担心反制成荒诞消毒动作，形成喜剧反差。",
                "evidence": ["63.430-64.750 来嘛，我帮你消毒！"],
            }
        ]
    }

    candidates = parse_punchline_candidates(raw, video_id="jialijiawai_ep01", duration_sec=220.0)

    assert candidates[0]["candidate_id"] == "punchline_jialijiawai_ep01_001"
    assert candidates[0]["source_branch"] == "punchline"
    assert candidates[0]["candidate_type"] == "punchline"
    assert candidates[0]["expression_type"] == "笑点"
    assert candidates[0]["start_time"] == 59.83
    assert candidates[0]["end_time"] == 68.15
    assert "trigger_time" not in candidates[0]
    assert candidates[0]["punchline_text"] == "来嘛，我帮你消毒！"
    assert candidates[0]["reason"] == "女主把领导对毒素的夸张担心反制成荒诞消毒动作，形成喜剧反差。"


def test_parse_punchline_candidates_rejects_missing_punchline_text() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 1.0,
                "end_time": 4.0,
                "summary": "普通剧情",
                "punchline_text": "",
                "reason": "",
                "evidence": [],
            }
        ]
    }

    assert parse_punchline_candidates(raw, video_id="demo_ep01", duration_sec=10.0) == []


def test_parse_punchline_candidates_rejects_long_emotional_conversation() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 170.87,
                "end_time": 203.18,
                "summary": "母亲嘴硬说不回来也没关系，儿子说要回家。",
                "punchline_text": "有钱没钱回家过年吗？",
                "reason": "母亲嘴硬和儿子回应形成反差。",
                "evidence": ["170.870-203.180 母子通电话"],
            }
        ]
    }

    assert parse_punchline_candidates(raw, video_id="beiwang_ep01", duration_sec=301.141) == []


def test_build_punchline_prompt_mentions_non_plot_boundary() -> None:
    prompt = build_punchline_prompt(
        video_id="demo_ep01",
        video_duration_seconds=120.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\n[1.000-2.000] 哈哈\n[/SUBTITLE_TIMELINE]",
        metadata={},
    )

    assert "short-drama punchline annotator" in prompt
    assert "expression-trigger" not in prompt
    assert "Punchline Branch" not in prompt
    assert "trigger_time" not in prompt
    assert "punchline_text" in prompt
    assert "comedic dialogue" in prompt
    assert "first utterance start time" in prompt
    assert "last utterance end time" in prompt
    assert "local performance" not in prompt
    assert "action plus dialogue" not in prompt
    assert "line/action" not in prompt
    assert "ordinary plot payoff" in prompt
    assert "Reject sincere family" in prompt
    assert "Do not label emotional contrast" in prompt
    assert "one or several consecutive utterances" in prompt
    assert '"start_time":63.43' in prompt
    assert '"end_time":64.75' in prompt

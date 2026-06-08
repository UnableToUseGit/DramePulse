from __future__ import annotations

import json
from pathlib import Path


class FakeLlmClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []
        self.last_call_diagnostics: dict[str, object] = {"status": "success", "usage": {"total_tokens": 64}}

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 4800,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_paths": image_paths or [],
                "frame_timestamps_seconds": frame_timestamps_seconds or [],
                "max_tokens": max_tokens,
            }
        )
        return self.response


def make_window_payload() -> dict[str, object]:
    return {
        "created_at": "2026-06-07T00:00:00Z",
        "source_csv": "data/圈选剧前5集弹幕.csv",
        "windows": [
            {
                "window_id": "dw_beiwang_ep01_001",
                "video_id": "beiwang_ep01",
                "start_time": 10.0,
                "end_time": 18.0,
                "resonance_score": 12.3,
                "actor_charm_ratio": 0.5,
                "emotion_burst_ratio": 0.0,
                "comments": [
                    {
                        "comment_id": "dm_1",
                        "time_sec": 11.0,
                        "text": "这个眼神太帅了",
                        "digg_count": 5,
                    },
                    {
                        "comment_id": "dm_2",
                        "time_sec": 12.0,
                        "text": "他看她的眼神绝了",
                        "digg_count": 2,
                    },
                ],
            }
        ],
    }


def test_build_window_semantic_prompt_contains_all_window_comments() -> None:
    from pipelines.danmaku_llm_refinement import build_window_semantic_prompt

    prompt = build_window_semantic_prompt(make_window_payload()["windows"][0])

    assert "同语义弹幕簇" in prompt
    assert "dm_1" in prompt
    assert "这个眼神太帅了" in prompt
    assert "他看她的眼神绝了" in prompt
    assert "sourceCommentIds" in prompt


def test_build_window_semantic_prompt_samples_large_comment_windows() -> None:
    from pipelines.danmaku_llm_refinement import build_window_semantic_prompt

    window = {
        "window_id": "dw_large_001",
        "video_id": "beiwang_ep01",
        "start_time": 0.0,
        "end_time": 8.0,
        "comments": [
            {
                "comment_id": f"dm_{index}",
                "time_sec": float(index),
                "text": f"第 {index} 条弹幕",
                "digg_count": index % 3,
            }
            for index in range(150)
        ],
    }

    first_prompt = build_window_semantic_prompt(window)
    second_prompt = build_window_semantic_prompt(window)

    assert first_prompt == second_prompt
    assert first_prompt.count('"commentId"') == 120
    assert "sampledCommentCount" in first_prompt
    assert "originalCommentCount" in first_prompt


def test_build_window_semantic_prompt_limits_requested_source_comment_ids() -> None:
    from pipelines.danmaku_llm_refinement import build_window_semantic_prompt

    prompt = build_window_semantic_prompt(make_window_payload()["windows"][0])

    assert "sourceCommentIds 最多返回 10 个" in prompt


def test_refine_danmaku_windows_with_llm_builds_grounded_candidates() -> None:
    from pipelines.danmaku_llm_refinement import refine_danmaku_windows_with_llm

    fake_client = FakeLlmClient(
        {
            "usable": True,
            "clusters": [
                {
                    "clusterType": "actor_charm",
                    "representativeText": "这个眼神太帅了",
                    "sourceCommentIds": ["dm_1", "dm_2"],
                    "confidence": 0.88,
                    "reason": "两条弹幕都在夸角色眼神。",
                },
                {
                    "clusterType": "other",
                    "representativeText": "哈哈哈",
                    "sourceCommentIds": ["dm_1"],
                    "confidence": 0.9,
                    "reason": "简单情绪表达，应该被过滤。",
                },
            ],
        }
    )

    result = refine_danmaku_windows_with_llm(
        make_window_payload(),
        llm_client=fake_client,
        max_tokens=900,
    )

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["max_tokens"] == 900
    assert result["llmWindowCount"] == 1
    assert result["candidateCount"] == 1
    candidate = result["candidates"][0]
    assert candidate["candidate_id"] == "ivllm_beiwang_ep01_001"
    assert candidate["video_id"] == "beiwang_ep01"
    assert candidate["window_id"] == "dw_beiwang_ep01_001"
    assert candidate["trigger_time"] == 11.0
    assert candidate["duration_sec"] == 5.0
    assert candidate["text"] == "这个眼神太帅了"
    assert candidate["cluster_type"] == "actor_charm"
    assert candidate["source_comment_ids"] == ["dm_1", "dm_2"]
    assert result["debug"]["filteredClusters"][0]["reason"] == "simple_emotion_text"


def test_refine_danmaku_windows_limits_source_comment_ids() -> None:
    from pipelines.danmaku_llm_refinement import refine_danmaku_windows_with_llm

    comments = [
        {"comment_id": f"dm_{index}", "time_sec": float(index), "text": f"这个眼神太帅了 {index}", "digg_count": 1}
        for index in range(12)
    ]
    fake_client = FakeLlmClient(
        {
            "usable": True,
            "clusters": [
                {
                    "clusterType": "actor_charm",
                    "representativeText": "这个眼神太帅了",
                    "sourceCommentIds": [f"dm_{index}" for index in range(12)],
                    "confidence": 0.9,
                    "reason": "多条弹幕都在夸眼神。",
                }
            ],
        }
    )

    result = refine_danmaku_windows_with_llm(
        {
            "windows": [
                {
                    "window_id": "dw_beiwang_ep01_001",
                    "video_id": "beiwang_ep01",
                    "start_time": 0.0,
                    "end_time": 8.0,
                    "comments": comments,
                }
            ]
        },
        llm_client=fake_client,
    )

    assert len(result["candidates"][0]["source_comment_ids"]) == 10
    assert result["candidates"][0]["source_comment_ids"] == [f"dm_{index}" for index in range(10)]


def test_refine_danmaku_windows_filters_invalid_source_ids() -> None:
    from pipelines.danmaku_llm_refinement import refine_danmaku_windows_with_llm

    fake_client = FakeLlmClient(
        {
            "usable": True,
            "clusters": [
                {
                    "clusterType": "actor_charm",
                    "representativeText": "这个眼神太帅了",
                    "sourceCommentIds": ["unknown_dm"],
                    "confidence": 0.92,
                    "reason": "source id 不在输入窗口中。",
                }
            ],
        }
    )

    result = refine_danmaku_windows_with_llm(make_window_payload(), llm_client=fake_client)

    assert result["candidates"] == []
    assert result["debug"]["filteredClusters"][0]["reason"] == "invalid_source_comment_ids"


def test_danmaku_llm_refinement_cli_writes_candidates(tmp_path: Path) -> None:
    from scripts.run_danmaku_llm_refinement import main

    windows_path = tmp_path / "resonance_windows.json"
    output_path = tmp_path / "inner_voice_llm_candidates.json"
    windows_path.write_text(json.dumps(make_window_payload(), ensure_ascii=False), encoding="utf-8")
    fake_client = FakeLlmClient(
        {
            "usable": True,
            "clusters": [
                {
                    "clusterType": "actor_charm",
                    "representativeText": "这个眼神太帅了",
                    "sourceCommentIds": ["dm_1", "dm_2"],
                    "confidence": 0.88,
                    "reason": "两条弹幕都在夸角色眼神。",
                }
            ],
        }
    )

    result = main(
        [
            "--windows-path",
            str(windows_path),
            "--output-path",
            str(output_path),
        ],
        llm_client=fake_client,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["candidateCount"] == 1
    assert payload["candidates"][0]["text"] == "这个眼神太帅了"


def test_danmaku_llm_refinement_cli_filters_series_and_episode(tmp_path: Path) -> None:
    from scripts.run_danmaku_llm_refinement import main

    payload = {
        "windows": [
            {
                "window_id": "dw_beiwang_ep01_001",
                "video_id": "beiwang_ep01",
                "start_time": 10.0,
                "end_time": 18.0,
                "comments": [
                    {"comment_id": "ep01_dm_1", "time_sec": 11.0, "text": "第一集", "digg_count": 1},
                ],
            },
            {
                "window_id": "dw_beiwang_ep02_001",
                "video_id": "beiwang_ep02",
                "start_time": 20.0,
                "end_time": 28.0,
                "comments": [
                    {"comment_id": "ep02_dm_1", "time_sec": 21.0, "text": "第二集这个眼神太帅了", "digg_count": 5},
                ],
            },
        ]
    }
    windows_path = tmp_path / "resonance_windows.json"
    output_path = tmp_path / "inner_voice_llm_candidates.json"
    windows_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    fake_client = FakeLlmClient(
        {
            "usable": True,
            "clusters": [
                {
                    "clusterType": "actor_charm",
                    "representativeText": "第二集这个眼神太帅了",
                    "sourceCommentIds": ["ep02_dm_1"],
                    "confidence": 0.88,
                    "reason": "只应该处理第二集窗口。",
                }
            ],
        }
    )

    result = main(
        [
            "--windows-path",
            str(windows_path),
            "--output-path",
            str(output_path),
            "--series-id",
            "beiwang",
            "--episode-id",
            "ep02",
        ],
        llm_client=fake_client,
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert len(fake_client.calls) == 1
    assert "beiwang_ep02" in str(fake_client.calls[0]["user_prompt"])
    assert "beiwang_ep01" not in str(fake_client.calls[0]["user_prompt"])
    assert output["llmWindowCount"] == 1
    assert output["candidates"][0]["video_id"] == "beiwang_ep02"


def test_danmaku_llm_refinement_cli_prints_window_progress(tmp_path: Path, capsys) -> None:
    from scripts.run_danmaku_llm_refinement import main

    windows_path = tmp_path / "resonance_windows.json"
    output_path = tmp_path / "inner_voice_llm_candidates.json"
    windows_path.write_text(json.dumps(make_window_payload(), ensure_ascii=False), encoding="utf-8")
    fake_client = FakeLlmClient(
        {
            "usable": True,
            "clusters": [
                {
                    "clusterType": "actor_charm",
                    "representativeText": "这个眼神太帅了",
                    "sourceCommentIds": ["dm_1", "dm_2"],
                    "confidence": 0.88,
                    "reason": "两条弹幕都在夸角色眼神。",
                }
            ],
        }
    )

    result = main(
        [
            "--windows-path",
            str(windows_path),
            "--output-path",
            str(output_path),
        ],
        llm_client=fake_client,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "prepared: windows=1" in captured.out
    assert "[beiwang_ep01] llm_window_start: 1/1 window=dw_beiwang_ep01_001 comments=2" in captured.out
    assert "[beiwang_ep01] llm_window_done: 1/1 window=dw_beiwang_ep01_001 candidates=1 filtered=0 tokens=64" in captured.out
    assert "completed: windows=1 candidates=1 filtered=0" in captured.out


def test_danmaku_llm_refinement_cli_prints_sampled_comment_count(tmp_path: Path, capsys) -> None:
    from scripts.run_danmaku_llm_refinement import main

    windows_path = tmp_path / "resonance_windows.json"
    output_path = tmp_path / "inner_voice_llm_candidates.json"
    payload = {
        "windows": [
            {
                "window_id": "dw_beiwang_ep01_large",
                "video_id": "beiwang_ep01",
                "start_time": 10.0,
                "end_time": 18.0,
                "comments": [
                    {
                        "comment_id": f"dm_{index}",
                        "time_sec": float(index),
                        "text": f"第 {index} 条弹幕",
                        "digg_count": index % 3,
                    }
                    for index in range(150)
                ],
            }
        ],
    }
    windows_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    fake_client = FakeLlmClient({"usable": False, "clusters": []})

    result = main(
        [
            "--windows-path",
            str(windows_path),
            "--output-path",
            str(output_path),
        ],
        llm_client=fake_client,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "[beiwang_ep01] llm_window_start: 1/1 window=dw_beiwang_ep01_large comments=150 sampled=120" in captured.out

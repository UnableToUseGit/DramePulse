from __future__ import annotations

import json
from pathlib import Path


def selection_payload() -> dict[str, object]:
    return {
        "videoId": "beiwang_ep02",
        "candidates": [
            {
                "candidateId": "ivcluster_beiwang_ep02_001",
                "videoId": "beiwang_ep02",
                "clusterId": "dsc_beiwang_ep02_033",
                "text": "这俩活宝太有戏了",
                "suitabilityScore": 0.92,
                "reason": "角色互动有共鸣。",
                "sourceCommentIds": ["dm_1", "dm_2"],
                "cluster": {
                    "scoreRank": 2,
                    "clusterScore": 128.5,
                    "commentCount": 44,
                    "peakIntervals": [
                        {"startTime": 31.2, "endTime": 39.2, "commentCount": 19},
                    ],
                },
            },
            {
                "candidateId": "ivcluster_beiwang_ep02_002",
                "videoId": "beiwang_ep02",
                "clusterId": "dsc_beiwang_ep02_016",
                "text": "这嗑唠得真硬啊",
                "suitabilityScore": 0.88,
                "sourceCommentIds": [],
                "cluster": {
                    "scoreRank": 40,
                    "clusterScore": 32.5,
                    "commentCount": 9,
                    "peakIntervals": [
                        {"startTime": 88.0, "endTime": 91.0, "commentCount": 5},
                    ],
                },
            },
        ],
        "debug": {"llmRawResult": {"selected": []}},
    }


def test_build_inner_voice_interaction_plan_uses_peak_interval_timing_without_debug() -> None:
    from pipelines.danmaku_interaction_plan import build_inner_voice_interaction_plan

    plan = build_inner_voice_interaction_plan(
        selection_payload(),
        series_id="beiwang",
        episode_id="ep02",
    )

    assert len(plan) == 2
    assert plan[0] == {
        "interaction_id": "ivp_beiwang_ep02_001",
        "video_id": "beiwang_ep02",
        "series_id": "beiwang",
        "episode_no": 2,
        "interaction_mode": "inner_voice_danmaku",
        "trigger_time": 31.2,
        "duration_sec": 8.0,
        "expire_time": 39.2,
        "content": {
            "text": "这俩活宝太有戏了",
            "candidate_id": "ivcluster_beiwang_ep02_001",
            "cluster_id": "dsc_beiwang_ep02_033",
            "suitability_score": 0.92,
            "source_comment_ids": ["dm_1", "dm_2"],
            "cluster_score_rank": 2,
            "cluster_score": 128.5,
            "cluster_comment_count": 44,
        },
    }
    assert "debug" not in plan[0]
    assert "send_action" not in plan[0]["content"]
    assert "display_style" not in plan[0]["content"]

    assert plan[1]["duration_sec"] == 5.0
    assert plan[1]["expire_time"] == 93.0


def test_build_inner_voice_interaction_plan_skips_candidates_without_peak_interval() -> None:
    from pipelines.danmaku_interaction_plan import build_inner_voice_interaction_plan

    payload = selection_payload()
    payload["candidates"] = [
        {
            "candidateId": "ivcluster_beiwang_ep02_001",
            "videoId": "beiwang_ep02",
            "clusterId": "dsc_beiwang_ep02_033",
            "text": "这俩活宝太有戏了",
            "suitabilityScore": 0.92,
            "cluster": {"peakIntervals": []},
        }
    ]

    assert build_inner_voice_interaction_plan(payload, series_id="beiwang", episode_id="ep02") == []


def test_interaction_plan_script_writes_plain_list(tmp_path: Path) -> None:
    from scripts.run_danmaku_interaction_plan import main

    selection_path = tmp_path / "selection.json"
    output_path = tmp_path / "interaction_plan.json"
    selection_path.write_text(json.dumps(selection_payload(), ensure_ascii=False), encoding="utf-8")

    result = main(
        [
            "--selection-path",
            str(selection_path),
            "--output-path",
            str(output_path),
            "--series-id",
            "beiwang",
            "--episode-id",
            "ep02",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert isinstance(payload, list)
    assert payload[0]["interaction_mode"] == "inner_voice_danmaku"
    assert "debug" not in payload[0]

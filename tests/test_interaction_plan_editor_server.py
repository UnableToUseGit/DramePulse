from __future__ import annotations

import json
from pathlib import Path


def make_episode(data_root: Path, *, series_id: str = "series_a", episode_id: str = "ep01") -> Path:
    episode_dir = data_root / series_id / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(b"video")
    (episode_dir / "douyin.json").write_text(
        json.dumps({"metadata": {"title": "测试短剧 第一集"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return episode_dir


def make_plan(plan_root: Path, *, video_id: str = "series_a_ep01", source: str = "from_expression_triggers") -> Path:
    plan_dir = plan_root / source / video_id
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "interaction_plan.json"
    interaction_id = f"ip_{video_id}_001" if source == "from_expression_triggers" else f"ivp_{video_id}_001"
    interaction_mode = "emotional_button" if source == "from_expression_triggers" else "inner_voice_danmaku"
    content = (
        {
            "expression_type": "爽点",
            "source_trigger_id": f"et_{video_id}_001",
            "source_start_time": 5.0,
            "source_end_time": 8.0,
        }
        if source == "from_expression_triggers"
        else {
            "text": "这老板真是好人啊",
            "candidate_id": f"ivcluster_{video_id}_001",
        }
    )
    plan_path.write_text(
        json.dumps(
            [
                {
                    "interaction_id": interaction_id,
                    "video_id": video_id,
                    "series_id": "series_a",
                    "episode_no": 1,
                    "interaction_mode": interaction_mode,
                    "trigger_time": 7.8 if source == "from_expression_triggers" else 9.2,
                    "duration_sec": 5.0,
                    "expire_time": 12.8 if source == "from_expression_triggers" else 14.2,
                    "content": content,
                }
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_path


def test_editor_indexes_episodes_with_interaction_plan(tmp_path: Path) -> None:
    from scripts.serve_interaction_plan_editor import build_episode_index

    data_root = tmp_path / "DataForAlgorithm"
    plan_root = tmp_path / "output" / "interaction_plan"
    curated_root = tmp_path / "output" / "interaction_plan_curated"
    make_episode(data_root)
    plan_path = make_plan(plan_root)

    index = build_episode_index(data_root=data_root, plan_root=plan_root, curated_root=curated_root)

    assert len(index["episodes"]) == 1
    episode = index["episodes"][0]
    assert episode["video_id"] == "series_a_ep01"
    assert episode["title"] == "测试短剧 第一集"
    assert episode["has_interaction_plan"] is True
    assert episode["interaction_plan_count"] == 1
    assert episode["interaction_plan_paths"] == [str(plan_path)]
    assert episode["has_curated_plan"] is False


def test_editor_loads_all_interaction_plan_sources_for_episode(tmp_path: Path) -> None:
    from scripts.serve_interaction_plan_editor import load_interaction_plan_payload

    plan_root = tmp_path / "output" / "interaction_plan"
    curated_root = tmp_path / "output" / "interaction_plan_curated"
    make_plan(plan_root, source="from_expression_triggers")
    make_plan(plan_root, source="inner_voice")

    payload = load_interaction_plan_payload(video_id="series_a_ep01", plan_root=plan_root, curated_root=curated_root)

    assert [item["interaction_id"] for item in payload["original_plan"]] == [
        "ip_series_a_ep01_001",
        "ivp_series_a_ep01_001",
    ]
    assert [item["_plan_source"] for item in payload["original_plan"]] == [
        "from_expression_triggers",
        "inner_voice",
    ]
    assert len(payload["source_plans"]) == 2
    assert payload["has_original_plan"] is True


def test_editor_loads_original_and_curated_plan(tmp_path: Path) -> None:
    from scripts.serve_interaction_plan_editor import load_interaction_plan_payload, write_curated_interaction_plan

    data_root = tmp_path / "DataForAlgorithm"
    plan_root = tmp_path / "output" / "interaction_plan"
    curated_root = tmp_path / "output" / "interaction_plan_curated"
    make_episode(data_root)
    make_plan(plan_root)
    edited_plan = [
        {
            "interaction_id": "ip_series_a_ep01_001",
            "video_id": "series_a_ep01",
            "series_id": "series_a",
            "episode_no": 1,
            "interaction_mode": "emotional_button",
            "trigger_time": 8.2,
            "duration_sec": 6.0,
            "expire_time": 14.2,
            "content": {
                "expression_type": "爽点",
                "source_trigger_id": "et_series_a_ep01_001",
                "source_start_time": 5.0,
                "source_end_time": 8.0,
                "note": "提前一点更贴合前端按钮。",
            },
        }
    ]
    write_curated_interaction_plan(
        video_id="series_a_ep01",
        plan=edited_plan,
        plan_root=plan_root,
        curated_root=curated_root,
    )

    payload = load_interaction_plan_payload(video_id="series_a_ep01", plan_root=plan_root, curated_root=curated_root)

    assert payload["video_id"] == "series_a_ep01"
    assert payload["original_plan"][0]["trigger_time"] == 7.8
    assert payload["curated_plan"][0]["trigger_time"] == 8.2
    assert payload["active_plan"][0]["duration_sec"] == 6.0
    assert payload["has_curated_plan"] is True


def test_editor_save_writes_curated_plan_and_edit_log(tmp_path: Path) -> None:
    from scripts.serve_interaction_plan_editor import write_curated_interaction_plan

    plan_root = tmp_path / "output" / "interaction_plan"
    curated_root = tmp_path / "output" / "interaction_plan_curated"
    make_plan(plan_root)

    plan = [
        {
            "interaction_id": "ip_series_a_ep01_001",
            "video_id": "series_a_ep01",
            "series_id": "series_a",
            "episode_no": 1,
            "interaction_mode": "emotional_button",
            "trigger_time": 8.2,
            "duration_sec": 6.0,
            "expire_time": 14.2,
            "content": {
                "expression_type": "甜点",
                "source_trigger_id": "et_series_a_ep01_001",
                "source_start_time": 5.0,
                "source_end_time": 8.0,
            },
        }
    ]

    result = write_curated_interaction_plan(
        video_id="series_a_ep01",
        plan=plan,
        plan_root=plan_root,
        curated_root=curated_root,
    )

    saved_plan = json.loads(result["curated_plan_path"].read_text(encoding="utf-8"))
    edit_log = json.loads(result["edit_log_path"].read_text(encoding="utf-8"))
    assert saved_plan == plan
    assert edit_log["video_id"] == "series_a_ep01"
    assert edit_log["edit_count"] == 3
    assert {edit["field"] for edit in edit_log["edits"]} == {
        "trigger_time",
        "duration_sec",
        "content.expression_type",
    }


def test_editor_edit_log_records_added_and_deleted_interactions(tmp_path: Path) -> None:
    from scripts.serve_interaction_plan_editor import write_curated_interaction_plan

    plan_root = tmp_path / "output" / "interaction_plan"
    curated_root = tmp_path / "output" / "interaction_plan_curated"
    make_plan(plan_root)

    result = write_curated_interaction_plan(
        video_id="series_a_ep01",
        plan=[
            {
                "interaction_id": "ip_series_a_ep01_manual_001",
                "video_id": "series_a_ep01",
                "series_id": "series_a",
                "episode_no": 1,
                "interaction_mode": "emotional_button",
                "trigger_time": 10.0,
                "duration_sec": 5.0,
                "expire_time": 15.0,
                "content": {
                    "expression_type": "笑点",
                    "source_trigger_id": "",
                    "source_start_time": 10.0,
                    "source_end_time": 10.0,
                },
            }
        ],
        plan_root=plan_root,
        curated_root=curated_root,
    )

    edit_log = json.loads(result["edit_log_path"].read_text(encoding="utf-8"))

    assert any(edit["action"] == "deleted" and edit["interaction_id"] == "ip_series_a_ep01_001" for edit in edit_log["edits"])
    assert any(edit["action"] == "added" and edit["interaction_id"] == "ip_series_a_ep01_manual_001" for edit in edit_log["edits"])

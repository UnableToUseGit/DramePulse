from __future__ import annotations

import json
from pathlib import Path


def write_exploration_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,0,哈哈哈",
                "北往,第1集,11000,3,她终于怼回去了",
                "北往,第1集,11600,2,她终于怼回去了",
                "北往,第1集,12500,5,太帅了这个眼神",
                "北往,第1集,40000,10,笑死我了",
                "北往,第1集,41000,1,笑不活了",
                "北往,第2集,9000,4,这谁顶得住",
                "北往,第2集,9500,1,禁止这么会演",
            ]
        )
        + "\n",
        encoding="gb18030",
    )


def test_explore_danmaku_csv_builds_profiles_windows_and_review_candidates(tmp_path: Path) -> None:
    from pipelines.danmaku_exploration import explore_danmaku_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    write_exploration_csv(csv_path)

    result = explore_danmaku_csv(
        csv_path,
        window_sec=8.0,
        step_sec=2.0,
        min_window_danmaku_count=2,
        max_windows_per_episode=5,
    )

    assert result["source_csv"] == str(csv_path)
    assert result["diagnostics"]["raw_row_count"] == 8
    assert result["episode_profiles"][0]["video_id"] == "beiwang_ep01"
    assert result["episode_profiles"][0]["danmaku_count"] == 6
    assert result["episode_profiles"][0]["low_quality_text_count"] == 1
    assert result["episode_profiles"][0]["top_repeated_texts"][0]["text"] == "她终于怼回去了"

    first_window = result["resonance_windows"][0]
    assert first_window["video_id"] == "beiwang_ep01"
    assert first_window["danmaku_count"] >= 3
    assert first_window["resonance_score"] > first_window["burst_score"]
    assert first_window["top_comments"][0]["text"] == "太帅了这个眼神"

    candidate_texts = [candidate["text"] for candidate in result["inner_voice_review_candidates"]]
    assert "她终于怼回去了" in candidate_texts
    accepted_candidate = next(candidate for candidate in result["inner_voice_review_candidates"] if candidate["text"] == "她终于怼回去了")
    assert accepted_candidate["intent_type"] == "plot_reaction"
    assert accepted_candidate["recommendation"] == "recommended"
    assert accepted_candidate["review_status"] == "unreviewed"
    assert accepted_candidate["source_comment_ids"]


def test_danmaku_exploration_cli_writes_three_artifacts(tmp_path: Path) -> None:
    from scripts.run_danmaku_exploration import main

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    output_root = tmp_path / "danmaku_exploration"
    write_exploration_csv(csv_path)

    result = main(
        [
            "--csv-path",
            str(csv_path),
            "--output-root",
            str(output_root),
            "--min-window-danmaku-count",
            "2",
        ]
    )

    assert result == 0
    profile = json.loads((output_root / "episode_profile.json").read_text(encoding="utf-8"))
    windows = json.loads((output_root / "resonance_windows.json").read_text(encoding="utf-8"))
    candidates = json.loads((output_root / "inner_voice_review_candidates.json").read_text(encoding="utf-8"))
    assert profile["episodes"][0]["video_id"] == "beiwang_ep01"
    assert windows["windows"]
    assert candidates["candidates"]

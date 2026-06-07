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
    assert len(first_window["comments"]) == first_window["danmaku_count"]
    assert first_window["comments"] == sorted(first_window["comments"], key=lambda comment: comment["time_sec"])

    candidate_texts = [candidate["text"] for candidate in result["inner_voice_review_candidates"]]
    assert "太帅了这个眼神" in candidate_texts
    accepted_candidate = next(candidate for candidate in result["inner_voice_review_candidates"] if candidate["text"] == "太帅了这个眼神")
    assert accepted_candidate["intent_type"] == "actor_charm"
    assert accepted_candidate["recommendation"] == "recommended"
    assert accepted_candidate["review_status"] == "unreviewed"
    assert accepted_candidate["source_comment_ids"]


def test_explore_danmaku_csv_filters_windows_with_only_simple_emotion(tmp_path: Path) -> None:
    from pipelines.danmaku_exploration import explore_danmaku_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    csv_path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,8,哈哈哈哈",
                "北往,第1集,10800,5,[捂脸][捂脸]",
                "北往,第1集,11600,3,笑死我了",
                "北往,第1集,12400,1,[哭]",
                "北往,第1集,50000,2,女主终于怼回去了",
                "北往,第1集,50800,1,她这句太争气了",
                "北往,第1集,51600,3,这个眼神太帅了",
                "北往,第1集,52400,0,他的表情也好帅",
            ]
        )
        + "\n",
        encoding="gb18030",
    )

    result = explore_danmaku_csv(
        csv_path,
        window_sec=8.0,
        step_sec=2.0,
        min_window_danmaku_count=4,
        max_windows_per_episode=10,
    )

    assert [window["start_time"] for window in result["resonance_windows"]] == [46.0]
    selected_window = result["resonance_windows"][0]
    assert selected_window["actor_charm_count"] == 2
    assert selected_window["actor_charm_ratio"] == 0.5
    assert selected_window["emotion_burst_count"] == 0
    assert selected_window["recall_reason"] == "actor_charm_ratio"


def test_actor_charm_single_hit_does_not_override_dense_emotion_burst(tmp_path: Path) -> None:
    from pipelines.danmaku_exploration import explore_danmaku_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    csv_path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,8,哈哈哈哈",
                "北往,第1集,10800,5,[捂脸][捂脸]",
                "北往,第1集,11600,3,笑死我了",
                "北往,第1集,12400,1,这个眼神太帅了",
            ]
        )
        + "\n",
        encoding="gb18030",
    )

    result = explore_danmaku_csv(
        csv_path,
        window_sec=8.0,
        step_sec=2.0,
        min_window_danmaku_count=4,
        max_windows_per_episode=10,
    )

    assert result["resonance_windows"] == []


def test_explore_danmaku_csv_filters_emoji_marker_only_rows(tmp_path: Path) -> None:
    from pipelines.danmaku_exploration import explore_danmaku_csv

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    csv_path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,8,[爽][爽][爽]",
                "北往,第1集,10800,5,[捂脸]",
                "北往,第1集,11600,3,这个眼神太帅了",
                "北往,第1集,12400,1,老公好帅",
            ]
        )
        + "\n",
        encoding="gb18030",
    )

    result = explore_danmaku_csv(
        csv_path,
        window_sec=8.0,
        step_sec=2.0,
        min_window_danmaku_count=2,
        max_windows_per_episode=10,
    )

    assert result["diagnostics"]["raw_row_count"] == 4
    assert result["diagnostics"]["normalized_row_count"] == 2
    assert result["diagnostics"]["skipped_reasons"] == {"emoji_marker_only": 2}
    assert result["episode_profiles"][0]["danmaku_count"] == 2
    assert {comment["text"] for comment in result["resonance_windows"][0]["comments"]} == {
        "这个眼神太帅了",
        "老公好帅",
    }


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

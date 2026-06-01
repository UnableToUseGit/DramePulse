from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def write_danmaku_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,0,哈哈哈哈",
                "北往,第1集,11200,4,笑死我了",
                "北往,第1集,13100,1,笑不活了",
                "北往,第1集,42000,3,太帅了这个眼神",
                "北往,第1集,43500,0,老公好帅",
                "北往,第1集,70000,2,我一定要出人头地燃起来了",
                "北往,第2集,9000,0,第二集笑死",
            ]
        )
        + "\n",
        encoding="gb18030",
    )


def test_analyze_episode_danmaku_groups_expression_peaks() -> None:
    from scripts.analyze_danmaku_expression_triggers import analyze_episode_danmaku

    items = [
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 10.0, "text": "哈哈哈哈", "digg_count": 0},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 11.2, "text": "笑死我了", "digg_count": 4},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 13.1, "text": "笑不活了", "digg_count": 1},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 42.0, "text": "太帅了这个眼神", "digg_count": 3},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 43.5, "text": "老公好帅", "digg_count": 0},
    ]

    result = analyze_episode_danmaku(
        video_id="beiwang_ep01",
        series_id="beiwang",
        episode_id="ep01",
        items=items,
        cluster_gap_sec=8.0,
        min_cluster_score=2.0,
    )

    assert result["video_id"] == "beiwang_ep01"
    assert result["total_danmaku_count"] == 5
    assert result["classified_danmaku_count"] == 5
    assert [cluster["expression_candidates"][0]["primary_expression"] for cluster in result["clusters"]] == ["笑死", "角色魅力"]
    laugh_cluster = result["clusters"][0]
    assert laugh_cluster["start_time"] == 9.0
    assert laugh_cluster["end_time"] == 15.1
    assert laugh_cluster["peak_time"] == 11.2
    assert laugh_cluster["suggested_trigger_time_range"] == [6.2, 11.2]
    assert laugh_cluster["suggested_cue_time_range"] == [10.2, 14.2]
    assert laugh_cluster["top_comments"][0]["text"] == "笑死我了"


def test_analyze_episode_danmaku_keeps_dense_distant_peaks_separate_by_expression() -> None:
    from scripts.analyze_danmaku_expression_triggers import analyze_episode_danmaku

    items = [
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 10.0, "text": "笑死我了", "digg_count": 0},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 12.0, "text": "哈哈哈哈", "digg_count": 0},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 17.5, "text": "好帅", "digg_count": 0},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 22.0, "text": "笑不活了", "digg_count": 3},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 25.0, "text": "老公好帅", "digg_count": 0},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 80.0, "text": "看哭了", "digg_count": 0},
        {"series_id": "beiwang", "episode_id": "ep01", "time_sec": 82.0, "text": "泪目", "digg_count": 0},
    ]

    result = analyze_episode_danmaku(
        video_id="beiwang_ep01",
        series_id="beiwang",
        episode_id="ep01",
        items=items,
        cluster_gap_sec=8.0,
        min_cluster_score=2.0,
    )

    labels = [cluster["expression_candidates"][0]["primary_expression"] for cluster in result["clusters"]]
    assert labels == ["笑死", "角色魅力", "笑死", "看哭了"]
    assert result["clusters"][0]["end_time"] < result["clusters"][1]["start_time"]
    assert result["clusters"][2]["end_time"] < result["clusters"][3]["start_time"]


def test_classify_text_does_not_treat_laugh_cry_emoji_as_tearful_expression() -> None:
    from scripts.analyze_danmaku_expression_triggers import classify_text

    assert classify_text("本来想划走，一看是他，看吧[笑哭][笑哭]") == []
    assert classify_text("看哭了居然") == ["看哭了"]


def test_main_writes_episode_analysis_outputs_from_csv(tmp_path: Path) -> None:
    from scripts.analyze_danmaku_expression_triggers import main

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    output_root = tmp_path / "analysis"
    write_danmaku_csv(csv_path)

    result = main(
        [
            "--csv-path",
            str(csv_path),
            "--output-root",
            str(output_root),
            "--min-cluster-score",
            "1.0",
        ]
    )

    ep01_path = output_root / "beiwang_ep01" / "danmaku_expression_analysis.json"
    ep02_path = output_root / "beiwang_ep02" / "danmaku_expression_analysis.json"
    summary_path = output_root / "summary.json"
    payload = json.loads(ep01_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert result == 0
    assert ep01_path.exists()
    assert ep02_path.exists()
    assert payload["series_id"] == "beiwang"
    assert {cluster["expression_candidates"][0]["primary_expression"] for cluster in payload["clusters"]} >= {"笑死", "角色魅力", "燃起来了"}
    assert summary["episode_count"] == 2
    assert summary["cluster_count"] >= 4

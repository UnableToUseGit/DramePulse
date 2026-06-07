from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def write_annotation(path: Path, *, video_id: str, annotations: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "video_id": video_id,
                "annotations": annotations,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_algorithm_output(path: Path, *, video_id: str, triggers: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "video_id": video_id,
                "expression_triggers": triggers,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_evaluate_episode_matches_nearest_trigger_with_expression_agreement() -> None:
    from scripts.evaluate_expression_trigger_annotations import evaluate_episode

    gold = [
        {
            "annotation_id": "gold_demo_ep01_001",
            "cue_time": 10.0,
            "primary_expression": "笑死",
            "reason": "笑点",
        },
        {
            "annotation_id": "gold_demo_ep01_002",
            "cue_time": 30.0,
            "primary_expression": "爽到了",
            "reason": "打脸",
        },
    ]
    predictions = [
        {"trigger_id": "et_demo_ep01_001", "cue_time": 10.8, "primary_expression": "笑死"},
        {"trigger_id": "et_demo_ep01_002", "cue_time": 33.0, "primary_expression": "震惊"},
        {"trigger_id": "et_demo_ep01_003", "cue_time": 60.0, "primary_expression": "笑死"},
    ]

    result = evaluate_episode(
        video_id="demo_ep01",
        gold_annotations=gold,
        predictions=predictions,
        tolerance_sec=3.0,
    )

    assert result["video_id"] == "demo_ep01"
    assert result["gold_count"] == 2
    assert result["prediction_count"] == 3
    assert result["matched_count"] == 2
    assert result["expression_correct_count"] == 1
    assert result["missed_count"] == 0
    assert result["false_positive_count"] == 1
    assert result["recall"] == 1.0
    assert result["precision"] == 0.666667
    assert result["expression_accuracy_on_matches"] == 0.5
    assert result["matches"][0]["time_delta_sec"] == 0.8
    assert result["matches"][0]["expression_match"] is True
    assert result["matches"][1]["expression_match"] is False
    assert result["false_positives"][0]["trigger_id"] == "et_demo_ep01_003"


def test_evaluate_episode_reads_prediction_trigger_time() -> None:
    from scripts.evaluate_expression_trigger_annotations import evaluate_episode

    result = evaluate_episode(
        video_id="demo_ep01",
        gold_annotations=[
            {
                "annotation_id": "gold_demo_ep01_001",
                "cue_time": 10.0,
                "primary_expression": "笑死",
                "reason": "笑点",
            }
        ],
        predictions=[
            {"trigger_id": "et_demo_ep01_001", "trigger_time": 10.5, "expression_type": "笑点"},
        ],
        tolerance_sec=3.0,
    )

    assert result["matched_count"] == 1
    assert result["matches"][0]["prediction"]["cue_time"] == 10.5
    assert result["matches"][0]["expression_match"] is True


def test_evaluate_episode_reports_unsupported_gold_expression() -> None:
    from scripts.evaluate_expression_trigger_annotations import evaluate_episode

    result = evaluate_episode(
        video_id="demo_ep01",
        gold_annotations=[
            {
                "annotation_id": "gold_demo_ep01_001",
                "cue_time": 20.0,
                "primary_expression": "震惊",
                "reason": "突然求婚。",
            }
        ],
        predictions=[
            {"trigger_id": "et_demo_ep01_001", "trigger_time": 20.2, "expression_type": "笑点"},
        ],
        tolerance_sec=3.0,
    )

    assert result["unsupported_gold_count"] == 1
    assert result["matched_count"] == 1
    assert result["supported_matched_count"] == 0
    assert result["expression_accuracy_on_matches"] is None
    assert result["matches"][0]["unsupported_gold_expression"] is True


def test_evaluate_episode_matches_payoff_time_inside_gold_window() -> None:
    from scripts.evaluate_expression_trigger_annotations import evaluate_episode

    gold = [
        {
            "annotation_id": "gold_demo_ep01_001",
            "payoff_time": 222.9,
            "payoff_window": {"start_time": 212.0, "end_time": 225.0},
            "primary_expression": "泪点",
            "reason": "母亲转悲为喜。",
        }
    ]
    predictions = [
        {"trigger_id": "et_demo_ep01_001", "payoff_time": 213.0, "primary_expression": "泪点"},
        {"trigger_id": "et_demo_ep01_002", "payoff_time": 260.0, "primary_expression": "笑点"},
    ]

    result = evaluate_episode(
        video_id="demo_ep01",
        gold_annotations=gold,
        predictions=predictions,
        tolerance_sec=3.0,
    )

    assert result["matched_count"] == 1
    assert result["matches"][0]["time_delta_sec"] == 9.9
    assert result["matches"][0]["matched_by"] == "payoff_window"
    assert result["false_positive_count"] == 1


def test_main_reads_annotation_directory_and_writes_report(tmp_path: Path) -> None:
    from scripts.evaluate_expression_trigger_annotations import main

    annotation_dir = tmp_path / "annotations"
    algorithm_output_root = tmp_path / "expression_trigger"
    report_path = tmp_path / "report.json"

    write_annotation(
        annotation_dir / "demo_ep01.annotation.json",
        video_id="demo_ep01",
        annotations=[
            {"annotation_id": "gold_demo_ep01_001", "cue_time": 10.0, "primary_expression": "笑死", "reason": "笑点"},
        ],
    )
    write_annotation(
        annotation_dir / "demo_ep02.annotation.json",
        video_id="demo_ep02",
        annotations=[],
    )
    write_algorithm_output(
        algorithm_output_root / "demo_ep01" / "expression_triggers.json",
        video_id="demo_ep01",
        triggers=[
            {"trigger_id": "et_demo_ep01_001", "cue_time": 11.0, "expression_type": "笑点"},
            {"trigger_id": "et_demo_ep01_002", "cue_time": 90.0, "expression_type": "爽点"},
        ],
    )

    result = main(
        [
            "--annotation-dir",
            str(annotation_dir),
            "--algorithm-output-root",
            str(algorithm_output_root),
            "--report-path",
            str(report_path),
            "--tolerance-sec",
            "3",
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result == 0
    assert report["summary"]["episode_count"] == 2
    assert report["summary"]["gold_count"] == 1
    assert report["summary"]["prediction_count"] == 2
    assert report["summary"]["matched_count"] == 1
    assert report["summary"]["false_positive_count"] == 1
    assert report["summary"]["unsupported_gold_count"] == 0
    assert report["episodes"][0]["video_id"] == "demo_ep01"
    assert report["episodes"][0]["algorithm_output_path"] == str(
        algorithm_output_root / "demo_ep01" / "expression_triggers.json"
    )
    assert report["episodes"][1]["video_id"] == "demo_ep02"
    assert report["episodes"][1]["missing_algorithm_output"] is True

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def make_expression_triggers(root: Path, *, video_id: str, series_id: str) -> None:
    output_dir = root / video_id
    output_dir.mkdir(parents=True)
    (output_dir / "expression_triggers.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "series_id": series_id,
                "created_at": "2026-06-07T00:00:00Z",
                "expression_triggers": [
                    {
                        "trigger_id": f"et_{video_id}_001",
                        "start_time": 5.0,
                        "end_time": 8.0,
                        "trigger_time": 7.8,
                        "expression_type": "爽点",
                        "importance_score": 0.91,
                        "summary": "女主反击。",
                        "reason": "反击完成。",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_interaction_plan_batch_writes_plan_from_expression_triggers(tmp_path: Path) -> None:
    from scripts.expression_trigger.run_interaction_plan_batch import main

    expression_root = tmp_path / "expression_trigger"
    output_root = tmp_path / "interaction_plan"
    make_expression_triggers(expression_root, video_id="series_a_ep01", series_id="series_a")

    result = main(
        [
            "--expression-trigger-root",
            str(expression_root),
            "--output-root",
            str(output_root),
        ]
    )

    output_path = output_root / "series_a_ep01" / "interaction_plan.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 0
    assert payload == [
        {
            "interaction_id": "ip_series_a_ep01_001",
            "video_id": "series_a_ep01",
            "series_id": "series_a",
            "episode_no": 1,
            "interaction_mode": "emotional_button",
            "trigger_time": 7.8,
            "duration_sec": 5.0,
            "expire_time": 12.8,
            "content": {
                "expression_type": "爽点",
                "source_trigger_id": "et_series_a_ep01_001",
                "source_start_time": 5.0,
                "source_end_time": 8.0,
            },
        }
    ]


def test_interaction_plan_batch_skips_existing_output(tmp_path: Path, capsys) -> None:
    from scripts.expression_trigger.run_interaction_plan_batch import main

    expression_root = tmp_path / "expression_trigger"
    output_root = tmp_path / "interaction_plan"
    make_expression_triggers(expression_root, video_id="series_a_ep01", series_id="series_a")
    output_path = output_root / "series_a_ep01" / "interaction_plan.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("[]\n", encoding="utf-8")

    result = main(
        [
            "--expression-trigger-root",
            str(expression_root),
            "--output-root",
            str(output_root),
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "SKIP series_a_ep01" in captured.out


def test_interaction_plan_batch_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/expression_trigger/run_interaction_plan_batch.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Build emotional button interaction plans" in result.stdout

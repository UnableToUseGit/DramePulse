from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_algorithm_expression_trigger_batch_scripts_do_not_import_legacy_root_scripts() -> None:
    script_paths = [
        REPO_ROOT / "scripts/expression_trigger/run_mllm_baseline_batch.py",
        REPO_ROOT / "scripts/expression_trigger/run_text_baseline_batch.py",
        REPO_ROOT / "scripts/expression_trigger/run_workflow_batch.py",
    ]

    for script_path in script_paths:
        source = script_path.read_text(encoding="utf-8")
        assert "from scripts.run_" not in source
        assert "import scripts.run_" not in source

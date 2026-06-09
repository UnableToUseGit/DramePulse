from __future__ import annotations

from pathlib import Path


def test_pipeline_utils_wrapper_is_removed() -> None:
    assert not Path("pipelines/utils.py").exists()

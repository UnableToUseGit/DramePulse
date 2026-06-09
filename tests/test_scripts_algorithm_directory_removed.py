from __future__ import annotations

from pathlib import Path


def test_scripts_algorithm_directory_is_removed() -> None:
    assert not Path("scripts/algorithm").exists()

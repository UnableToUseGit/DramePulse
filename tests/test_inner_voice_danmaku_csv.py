from __future__ import annotations

from pathlib import Path


def test_inner_voice_danmaku_csv_maps_chinese_series_title() -> None:
    from pipelines.inner_voice_danmaku.danmaku_csv import SERIES_SLUGS, normalize_episode_id

    assert SERIES_SLUGS["北往"] == "beiwang"
    assert SERIES_SLUGS["家里家外"] == "jialijiawai"
    assert normalize_episode_id("第3集") == "ep03"


def test_inner_voice_exploration_does_not_depend_on_scripts_layer() -> None:
    source = Path("pipelines/inner_voice_danmaku/exploration.py").read_text(encoding="utf-8")

    assert "scripts.algorithm_danmaku_csv" not in source


def test_algorithm_danmaku_csv_wrapper_is_removed() -> None:
    assert not Path("scripts/algorithm_danmaku_csv.py").exists()

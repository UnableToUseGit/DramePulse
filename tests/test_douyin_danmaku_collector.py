from pathlib import Path

import pytest

from scripts import douyin_danmaku_collector as collector


def write_csv(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_csv_manifest_with_header(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "targets.csv",
        "series_name,episode_no,douyin_video_id\n"
        "北派寻宝笔记,63,7546166458309430554\n",
    )

    episodes = collector.load_csv_manifest(csv_path)

    assert episodes == [
        {
            "episode_id": "7546166458309430554",
            "video_id": "7546166458309430554",
            "video_url": "https://www.douyin.com/video/7546166458309430554",
            "series_name": "北派寻宝笔记",
            "series_id": "beipai_xunbao_biji",
            "episode_no": "63",
            "episode_label": "ep63",
        }
    ]


def test_load_csv_manifest_without_header(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "targets.csv",
        "北派寻宝笔记,第64集,douyin_7546166458309430555\n",
    )

    [episode] = collector.load_csv_manifest(csv_path)

    assert episode["video_id"] == "7546166458309430555"
    assert episode["series_id"] == "beipai_xunbao_biji"
    assert episode["episode_no"] == "64"
    assert episode["episode_label"] == "ep64"


@pytest.mark.parametrize(
    ("raw", "expected_no", "expected_label"),
    [
        ("1", "1", "ep01"),
        ("01", "1", "ep01"),
        ("ep8", "8", "ep08"),
        ("第18集", "18", "ep18"),
        ("63", "63", "ep63"),
    ],
)
def test_normalize_episode_no(raw: str, expected_no: str, expected_label: str) -> None:
    assert collector.normalize_episode_no(raw) == (expected_no, expected_label)


def test_load_csv_manifest_rejects_unknown_series(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "targets.csv",
        "series_name,episode_no,douyin_video_id\n"
        "未知短剧,1,7546166458309430554\n",
    )

    with pytest.raises(ValueError, match="unknown series_name"):
        collector.load_csv_manifest(csv_path)


def test_episode_output_path_uses_dataset_layout() -> None:
    episode = {
        "video_id": "7546166458309430554",
        "series_id": "beipai_xunbao_biji",
        "episode_label": "ep63",
    }

    assert collector.episode_output_path(
        Path("/data/VideoData"),
        episode,
        dataset_layout=True,
    ) == Path("/data/VideoData/raw/beipai_xunbao_biji/ep63/douyin.json")


def test_episode_output_path_keeps_legacy_flat_layout() -> None:
    episode = {"video_id": "7546166458309430554"}

    assert collector.episode_output_path(
        Path("data/raw/episodes"),
        episode,
        dataset_layout=False,
    ) == Path("data/raw/episodes/douyin_7546166458309430554.json")


def test_parser_accepts_csv_and_output_dir() -> None:
    args = collector.build_parser().parse_args(
        [
            "--csv",
            "targets.csv",
            "--output-dir",
            "/data/VideoData",
        ]
    )

    assert args.csv == Path("targets.csv")
    assert args.output_dir == Path("/data/VideoData")


def test_parser_keeps_legacy_manifest_and_out_dir() -> None:
    args = collector.build_parser().parse_args(
        [
            "--manifest",
            "configs/douyin_episodes.json",
            "--out-dir",
            "data/raw/episodes",
        ]
    )

    assert args.manifest == Path("configs/douyin_episodes.json")
    assert args.out_dir == Path("data/raw/episodes")
    assert args.csv is None

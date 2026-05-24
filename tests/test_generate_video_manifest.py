from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import generate_video_manifest


def write_douyin_json(path: Path, *, video_id: str = "7622167244545609002") -> None:
    path.write_text(
        json.dumps(
            {
                "source": "douyin",
                "episode_id": video_id,
                "video_id": video_id,
                "video_url": f"https://www.douyin.com/video/{video_id}",
                "metadata": {
                    "title": "北派寻宝笔记 第63集 高燃片段",
                    "duration_ms": 123450,
                },
                "danmaku": {
                    "count": 2,
                    "items": [
                        {"time_sec": 1.2, "text": "来了"},
                        {"time_sec": 3.4, "text": "好看"},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def make_episode(data_root: Path) -> Path:
    episode_dir = data_root / "raw" / "beipai_xunbao_biji" / "ep63"
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(b"fake video")
    write_douyin_json(episode_dir / "douyin.json")
    return episode_dir


def test_generate_manifest_from_video_data_root(tmp_path: Path) -> None:
    make_episode(tmp_path)

    manifest = generate_video_manifest.generate_manifest(tmp_path)

    assert manifest["schema_version"] == "video_manifest.v1"
    assert len(manifest["videos"]) == 1
    assert manifest["videos"][0] == {
        "video_id": "beipai_xunbao_biji_ep63",
        "series_id": "beipai_xunbao_biji",
        "series_name": "北派寻宝笔记",
        "episode_no": 63,
        "episode_label": "ep63",
        "title": "北派寻宝笔记 第63集 高燃片段",
        "duration": 123.45,
        "source": "local",
        "status": "active",
        "storage": {
            "bucket": "local",
            "object_key": "raw/beipai_xunbao_biji/ep63/video.mp4",
            "content_type": "video/mp4",
            "size": len(b"fake video"),
        },
        "douyin": {
            "video_id": "7622167244545609002",
            "video_url": "https://www.douyin.com/video/7622167244545609002",
            "json_path": "raw/beipai_xunbao_biji/ep63/douyin.json",
            "danmaku_count": 2,
            "available": True,
        },
    }


def test_write_manifest_defaults_to_data_root(tmp_path: Path) -> None:
    make_episode(tmp_path)

    output_path = generate_video_manifest.write_manifest(tmp_path)

    assert output_path == tmp_path / "video_manifest.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["videos"][0]["video_id"] == "beipai_xunbao_biji_ep63"


def test_generate_manifest_requires_douyin_json(tmp_path: Path) -> None:
    episode_dir = tmp_path / "raw" / "beipai_xunbao_biji" / "ep63"
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(b"fake video")

    manifest = generate_video_manifest.generate_manifest(tmp_path)

    assert manifest["videos"][0]["title"] == "北派寻宝笔记 ep63"
    assert manifest["videos"][0]["duration"] is None
    assert manifest["videos"][0]["douyin"] == {
        "video_id": None,
        "video_url": None,
        "json_path": None,
        "danmaku_count": 0,
        "available": False,
    }

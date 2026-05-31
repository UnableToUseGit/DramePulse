from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def make_episode(data_root: Path, *, series_id: str = "demo_series", episode_id: str = "ep01") -> Path:
    episode_dir = data_root / series_id / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(bytes(index % 251 for index in range(4096)))
    (episode_dir / "video.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")
    (episode_dir / "scene_detection.json").write_text(
        json.dumps({"scenes": [{"scene_id": "s1", "start_time": 0, "end_time": 2}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (episode_dir / "douyin.json").write_text(
        json.dumps(
            {
                "metadata": {"title": "测试短剧 第一集"},
                "danmaku": {"items": [{"time_sec": 1.2, "text": "来了"}]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return episode_dir


def test_review_server_scans_dataset_and_resolves_algorithm_output(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root)
    output_dir = output_root / "demo_series_ep01"
    output_dir.mkdir(parents=True)
    (output_dir / "highlight_recognition.json").write_text(
        json.dumps({"expression_triggers": [{"trigger_id": "et_001"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    from scripts.serve_algorithm_review_tool import build_episode_index

    index = build_episode_index(data_root=data_root, output_root=output_root)

    assert index["dataset_root"] == str(data_root)
    assert len(index["episodes"]) == 1
    episode = index["episodes"][0]
    assert episode["video_id"] == "demo_series_ep01"
    assert episode["title"] == "测试短剧 第一集"
    assert episode["has_danmaku"] is True
    assert episode["algorithm_output_type"] == "highlight_recognition"
    assert episode["algorithm_output_path"] == str(output_dir / "highlight_recognition.json")
    assert episode["feedback_path"] == str(output_dir / "expression_trigger_feedback.json")


def test_review_server_saves_feedback_under_output_root(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root)

    from scripts.serve_algorithm_review_tool import save_feedback_payload

    output_path = save_feedback_payload(
        video_id="demo_series_ep01",
        output_root=output_root,
        payload={"video_id": "demo_series_ep01", "trigger_reviews": []},
    )

    assert output_path == output_root / "demo_series_ep01" / "expression_trigger_feedback.json"
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["video_id"] == "demo_series_ep01"
    assert "saved_at" in saved


def test_review_server_http_serves_range_video_and_feedback_api(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    video_file = make_episode(data_root) / "video.mp4"

    server = subprocess.Popen(
        [
            sys.executable,
            "scripts/serve_algorithm_review_tool.py",
            "--port",
            "8783",
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    opener = build_opener(ProxyHandler({}))
    try:
        time.sleep(0.7)
        with opener.open("http://127.0.0.1:8783/api/episodes", timeout=5) as response:
            index = json.loads(response.read().decode("utf-8"))
        assert index["episodes"][0]["video_id"] == "demo_series_ep01"

        request = Request(
            "http://127.0.0.1:8783/api/episodes/demo_series_ep01/video",
            headers={"Range": "bytes=1000-1999"},
        )
        with opener.open(request, timeout=5) as response:
            body = response.read()
            assert response.status == 206
            assert response.headers.get("Content-Range") == "bytes 1000-1999/4096"
            assert body == video_file.read_bytes()[1000:2000]

        save_request = Request(
            "http://127.0.0.1:8783/api/episodes/demo_series_ep01/feedback",
            data=json.dumps({"video_id": "demo_series_ep01", "trigger_reviews": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(save_request, timeout=5) as response:
            saved_response = json.loads(response.read().decode("utf-8"))
        assert saved_response["ok"] is True
        assert (output_root / "demo_series_ep01" / "expression_trigger_feedback.json").exists()
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()


def test_review_server_rejects_unknown_video_feedback(tmp_path: Path) -> None:
    from scripts.serve_algorithm_review_tool import save_feedback_payload

    try:
        save_feedback_payload(video_id="../bad", output_root=tmp_path / "output", payload={"video_id": "../bad"})
    except ValueError as exc:
        assert "Invalid video_id" in str(exc)
    else:
        raise AssertionError("expected invalid video_id to be rejected")

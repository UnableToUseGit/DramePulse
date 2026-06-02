from __future__ import annotations

import json
from http import HTTPStatus
import socket
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


def write_danmaku_csv(data_root: Path) -> Path:
    path = data_root / "圈选剧前5集弹幕.csv"
    path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,1500,3,CSV弹幕更全",
                "北往,第2集,2500,1,第二集弹幕",
            ]
        )
        + "\n",
        encoding="gb18030",
    )
    return path


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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


def test_review_server_indexes_danmaku_csv_when_available(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="beiwang", episode_id="ep01")
    csv_path = write_danmaku_csv(data_root)

    from scripts.serve_algorithm_review_tool import build_episode_index

    index = build_episode_index(data_root=data_root, output_root=output_root)

    episode = index["episodes"][0]
    assert episode["video_id"] == "beiwang_ep01"
    assert episode["danmaku_path"] == str(csv_path)
    assert episode["danmaku_source"] == "csv"
    assert episode["has_danmaku"] is True


def test_review_server_scans_danmaku_csv_once_when_building_episode_index(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="beiwang", episode_id="ep01")
    make_episode(data_root, series_id="beiwang", episode_id="ep02")
    csv_path = write_danmaku_csv(data_root)

    from scripts import serve_algorithm_review_tool

    calls: list[Path] = []
    original_index = serve_algorithm_review_tool.index_danmaku_csv_episodes

    def tracked_index(data_root_arg: Path):
        calls.append(data_root_arg)
        return original_index(data_root_arg)

    monkeypatch.setattr(serve_algorithm_review_tool, "index_danmaku_csv_episodes", tracked_index)

    index = serve_algorithm_review_tool.build_episode_index(data_root=data_root, output_root=output_root)

    assert calls == [data_root]
    assert [episode["danmaku_path"] for episode in index["episodes"]] == [str(csv_path), str(csv_path)]
    assert [episode["danmaku_source"] for episode in index["episodes"]] == ["csv", "csv"]


def test_review_server_serves_csv_danmaku_before_douyin_json(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="beiwang", episode_id="ep01")
    write_danmaku_csv(data_root)

    from scripts.serve_algorithm_review_tool import load_episode_danmaku_payload

    payload = load_episode_danmaku_payload(data_root=data_root, episode_dir=data_root / "beiwang" / "ep01", series_id="beiwang", episode_id="ep01")

    assert payload["source"] == "csv"
    assert payload["count"] == 1
    assert payload["items"][0]["text"] == "CSV弹幕更全"
    assert payload["items"][0]["time_sec"] == 1.5
    assert payload["items"][0]["digg_count"] == 3


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


def test_review_server_loads_subtitle_density_payload(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root)
    density_dir = output_root / "subtitle_dialogue_density" / "demo_series_ep01"
    density_dir.mkdir(parents=True)
    density_path = density_dir / "subtitle_dialogue_density.json"
    density_path.write_text(
        json.dumps({"video_id": "demo_series_ep01", "density_windows": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    from scripts.serve_algorithm_review_tool import load_subtitle_density_payload

    payload = load_subtitle_density_payload(video_id="demo_series_ep01", output_root=output_root)

    assert payload["video_id"] == "demo_series_ep01"
    assert payload["_review_output_path"] == str(density_path)


def test_review_server_ignores_client_disconnect_during_range_video(tmp_path: Path) -> None:
    from scripts.serve_algorithm_review_tool import AlgorithmReviewHandler

    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(bytes(index % 251 for index in range(4096)))

    class BrokenWriter:
        def write(self, body: bytes) -> int:
            raise BrokenPipeError("client closed connection")

    handler = object.__new__(AlgorithmReviewHandler)
    handler.wfile = BrokenWriter()
    handler.responses: list[tuple[int, str]] = []
    handler.headers_sent: list[tuple[str, str]] = []
    handler.send_response = lambda status: handler.responses.append((status, ""))
    handler.send_header = lambda key, value: handler.headers_sent.append((key, value))
    handler.end_headers = lambda: None
    handler.guess_type = lambda path: "video/mp4"

    handler._send_file_range(video_file, (1000, 1999))

    assert handler.responses == [(HTTPStatus.PARTIAL_CONTENT, "")]
    assert ("Content-Range", "bytes 1000-1999/4096") in handler.headers_sent


def test_review_server_http_serves_range_video_and_feedback_api(tmp_path: Path) -> None:
    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    video_file = make_episode(data_root) / "video.mp4"
    port = find_free_port()

    server = subprocess.Popen(
        [
            sys.executable,
            "scripts/serve_algorithm_review_tool.py",
            "--port",
            str(port),
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
        with opener.open(f"http://127.0.0.1:{port}/api/episodes", timeout=5) as response:
            index = json.loads(response.read().decode("utf-8"))
        assert index["episodes"][0]["video_id"] == "demo_series_ep01"

        with opener.open(f"http://127.0.0.1:{port}/apps/annotation-tool/", timeout=5) as response:
            annotation_html = response.read().decode("utf-8")
        assert "DramePulse 高光标注" in annotation_html

        with opener.open(f"http://127.0.0.1:{port}/apps/annotation-tool/annotation_tool.js", timeout=5) as response:
            annotation_js = response.read().decode("utf-8")
        assert "normalizeVideoContext" in annotation_js

        with opener.open(f"http://127.0.0.1:{port}/apps/subtitle-density-tool/", timeout=5) as response:
            density_html = response.read().decode("utf-8")
        assert "字幕密度对照" in density_html

        with opener.open(f"http://127.0.0.1:{port}/apps/subtitle-density-tool/subtitle_density_tool.js", timeout=5) as response:
            density_js = response.read().decode("utf-8")
        assert "renderDensityTimeline" in density_js

        request = Request(
            f"http://127.0.0.1:{port}/api/episodes/demo_series_ep01/video",
            headers={"Range": "bytes=1000-1999"},
        )
        with opener.open(request, timeout=5) as response:
            body = response.read()
            assert response.status == 206
            assert response.headers.get("Content-Range") == "bytes 1000-1999/4096"
            assert body == video_file.read_bytes()[1000:2000]

        save_request = Request(
            f"http://127.0.0.1:{port}/api/episodes/demo_series_ep01/feedback",
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

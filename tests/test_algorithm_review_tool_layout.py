from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_review_tool_video_stays_inside_player_viewport() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert shutil.which("playwright-cli") is not None
    assert shutil.which("ffmpeg") is not None
    port = find_free_port()
    data_root = repo_root / ".tmp-review-layout-data"
    output_root = repo_root / ".tmp-review-layout-output"
    episode_dir = data_root / "vertical" / "ep01"
    if data_root.exists():
        shutil.rmtree(data_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n测试\n", encoding="utf-8")
    (episode_dir / "douyin.json").write_text(json.dumps({"metadata": {"title": "竖屏测试"}, "danmaku": {"items": []}}, ensure_ascii=False), encoding="utf-8")
    ffmpeg_result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=720x1280:d=1",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "faststart",
            str(episode_dir / "video.mp4"),
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert ffmpeg_result.returncode == 0, ffmpeg_result.stderr

    server = subprocess.Popen(
        [
            "python",
            "scripts/serve_algorithm_review_tool.py",
            "--port",
            str(port),
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
        ],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(0.5)
        open_result = subprocess.run(
            ["playwright-cli", "open", f"http://127.0.0.1:{port}/"],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert open_result.returncode == 0, open_result.stderr
        result = subprocess.run(
            [
                "playwright-cli",
                "--raw",
                "eval",
                """async () => {
                  const video = document.getElementById('video');
                  if (!video.videoWidth) {
                    await new Promise(resolve => video.addEventListener('loadedmetadata', resolve, { once: true }));
                  }
                  await new Promise(resolve => requestAnimationFrame(resolve));
                  const wrap = document.querySelector('.video-wrap').getBoundingClientRect();
                  const videoRect = video.getBoundingClientRect();
                  return JSON.stringify({
                    naturalWidth: video.videoWidth,
                    naturalHeight: video.videoHeight,
                    bodyScrollHeight: document.body.scrollHeight,
                    viewportHeight: window.innerHeight,
                    wrapHeight: wrap.height,
                    videoHeight: videoRect.height,
                    wrapWidth: wrap.width,
                    videoWidth: videoRect.width,
                  });
                }""",
            ],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        subprocess.run(["playwright-cli", "close"], cwd=repo_root, check=False, stdout=subprocess.PIPE)
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(data_root, ignore_errors=True)
        shutil.rmtree(output_root, ignore_errors=True)

    assert result.returncode == 0, result.stderr
    metrics = json.loads(json.loads(result.stdout))
    assert metrics["naturalWidth"] == 720
    assert metrics["naturalHeight"] == 1280
    assert metrics["videoHeight"] <= metrics["wrapHeight"] + 1
    assert metrics["videoWidth"] <= metrics["wrapWidth"] + 1
    assert metrics["bodyScrollHeight"] <= metrics["viewportHeight"] + 2

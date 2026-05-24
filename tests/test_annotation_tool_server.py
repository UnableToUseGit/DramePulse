from __future__ import annotations

import subprocess
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener


def test_annotation_server_supports_range_requests_for_video_seek(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    media_dir = tmp_path / "data" / "case1"
    media_dir.mkdir(parents=True)
    video_file = media_dir / "ep01.mp4"
    video_file.write_bytes(bytes(index % 251 for index in range(4096)))

    server = subprocess.Popen(
        ["python", str(repo_root / "scripts/serve_annotation_tool.py"), "--port", "8772", "--directory", str(tmp_path)],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(0.5)
        request = Request(
            "http://127.0.0.1:8772/data/case1/ep01.mp4",
            headers={"Range": "bytes=1000-1999"},
            method="GET",
        )
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=5) as response:
            body = response.read()
            status = response.status
            content_range = response.headers.get("Content-Range")
            accept_ranges = response.headers.get("Accept-Ranges")
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()

    assert status == 206
    assert len(body) == 1000
    assert accept_ranges == "bytes"
    assert content_range == "bytes 1000-1999/4096"
    assert body == video_file.read_bytes()[1000:2000]

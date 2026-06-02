from __future__ import annotations

import json
import shutil
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


def test_danmaku_panel_is_bounded_and_scrolls_inside_itself() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert shutil.which("playwright-cli") is not None

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/videos":
                self._send_json(
                    {
                        "videos": [
                            {
                                "video_id": "ep_10",
                                "series_name": "测试短剧",
                                "title": "第10集",
                                "episode_label": "ep10",
                                "stream_url": "/api/videos/ep_10/stream",
                                "danmaku_url": "/api/videos/ep_10/danmaku",
                            }
                        ]
                    }
                )
                return
            if self.path == "/api/videos/ep_10":
                self._send_json(
                    {
                        "video_id": "ep_10",
                        "series_name": "测试短剧",
                        "title": "第10集",
                        "episode_label": "ep10",
                        "stream_url": "/api/videos/ep_10/stream",
                        "danmaku_url": "/api/videos/ep_10/danmaku",
                    }
                )
                return
            if self.path == "/api/videos/ep_10/danmaku":
                self._send_json(
                    {
                        "video_id": "ep_10",
                        "available": True,
                        "count": 80,
                        "items": [
                            {
                                "danmaku_id": f"d_{index}",
                                "time_sec": index * 0.5,
                                "text": f"第 {index} 条弹幕",
                                "digg_count": index,
                                "score": index / 10,
                            }
                            for index in range(80)
                        ],
                    }
                )
                return
            return super().do_GET()

        def _send_json(self, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        playwright = ["playwright-cli", "-s=al"]
        open_result = subprocess.run(
            [*playwright, "open", f"http://127.0.0.1:{port}/apps/annotation-tool/"],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert open_result.returncode == 0, open_result.stderr
        subprocess.run(
            [
                *playwright,
                "--raw",
                "eval",
                """() => new Promise((resolve, reject) => {
                  const done = () => document.querySelectorAll('.danmaku-row').length === 80;
                  if (done()) return resolve(true);
                  const timer = setInterval(() => {
                    if (done()) {
                      clearInterval(timer);
                      clearTimeout(timeout);
                      resolve(true);
                    }
                  }, 50);
                  const timeout = setTimeout(() => {
                    clearInterval(timer);
                    reject(new Error(JSON.stringify({
                      rowCount: document.querySelectorAll('.danmaku-row').length,
                      status: document.getElementById('danmakuStatus')?.textContent,
                      listText: document.getElementById('danmakuList')?.textContent,
                      location: window.location.href,
                    })));
                  }, 5000);
                })""",
            ],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        result = subprocess.run(
            [
                *playwright,
                "--raw",
                "eval",
                """async () => {
                  window.scrollTo(0, 0);
                  const list = document.getElementById('danmakuList');
                  list.scrollTop = 5000;
                  await new Promise(resolve => setTimeout(resolve, 600));
                  return {
                    pageScrollY: window.scrollY,
                    danmakuScrollTop: list.scrollTop,
                    danmakuClientHeight: list.clientHeight,
                    danmakuScrollHeight: list.scrollHeight,
                    videoControlHitTag: (() => {
                      const video = document.getElementById('video');
                      const rect = video.getBoundingClientRect();
                      return document.elementFromPoint(rect.left + rect.width * 0.75, rect.bottom - 14)?.tagName;
                    })(),
                    bodyScrollHeight: document.documentElement.scrollHeight,
                    viewportHeight: window.innerHeight,
                  };
                }""",
            ],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        subprocess.run([*playwright, "close"], cwd=repo_root, check=False, stdout=subprocess.PIPE)
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()

    assert result.returncode == 0, result.stderr
    metrics = json.loads(result.stdout)
    assert metrics["pageScrollY"] == 0
    assert metrics["danmakuScrollTop"] > 0
    assert metrics["danmakuScrollHeight"] > metrics["danmakuClientHeight"]
    assert metrics["videoControlHitTag"] == "VIDEO"
    assert metrics["bodyScrollHeight"] <= metrics["viewportHeight"] + 2

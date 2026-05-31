from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from pathlib import Path
import re
from typing import Any, Sequence
from urllib.parse import unquote, urlparse


DEFAULT_DATA_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")
DEFAULT_OUTPUT_ROOT = Path("output")
TOOL_DIR = Path(__file__).resolve().parents[1] / "apps" / "algorithm-review-tool"
FEEDBACK_FILENAME = "expression_trigger_feedback.json"
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_valid_video_id(video_id: str) -> bool:
    return bool(VIDEO_ID_PATTERN.fullmatch(video_id)) and ".." not in video_id


def extract_title(episode_dir: Path, *, series_id: str, episode_id: str) -> str:
    payload = read_json(episode_dir / "douyin.json")
    if isinstance(payload, dict):
        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata.get("title"):
            return str(metadata["title"])
    return f"{series_id} {episode_id}"


def resolve_algorithm_output(video_id: str, output_root: Path) -> tuple[str | None, Path | None]:
    candidates = (
        ("highlight_recognition", output_root / video_id / "highlight_recognition.json"),
        ("highlight_candidates", output_root / video_id / "highlight_candidates.json"),
    )
    for output_type, path in candidates:
        if path.exists():
            return output_type, path
    return None, None


def build_episode_index(*, data_root: Path, output_root: Path) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    for video_path in sorted(data_root.glob("*/ep*/video.mp4")):
        episode_dir = video_path.parent
        series_id = episode_dir.parent.name
        episode_id = episode_dir.name
        video_id = f"{series_id}_{episode_id}"
        output_type, algorithm_output_path = resolve_algorithm_output(video_id, output_root)
        feedback_path = output_root / video_id / FEEDBACK_FILENAME
        episodes.append(
            {
                "video_id": video_id,
                "series_id": series_id,
                "episode_id": episode_id,
                "title": extract_title(episode_dir, series_id=series_id, episode_id=episode_id),
                "episode_dir": str(episode_dir),
                "video_path": str(video_path),
                "subtitle_path": str(episode_dir / "video.srt") if (episode_dir / "video.srt").exists() else None,
                "danmaku_path": str(episode_dir / "douyin.json") if (episode_dir / "douyin.json").exists() else None,
                "scene_detection_path": str(episode_dir / "scene_detection.json")
                if (episode_dir / "scene_detection.json").exists()
                else None,
                "has_subtitle": (episode_dir / "video.srt").exists(),
                "has_danmaku": (episode_dir / "douyin.json").exists(),
                "has_scene_detection": (episode_dir / "scene_detection.json").exists(),
                "algorithm_output_type": output_type,
                "algorithm_output_path": str(algorithm_output_path) if algorithm_output_path else None,
                "feedback_path": str(feedback_path),
                "has_feedback": feedback_path.exists(),
            }
        )
    return {
        "dataset_root": str(data_root),
        "output_root": str(output_root),
        "episodes": episodes,
    }


def save_feedback_payload(*, video_id: str, output_root: Path, payload: dict[str, Any]) -> Path:
    if not is_valid_video_id(video_id):
        raise ValueError(f"Invalid video_id: {video_id}")
    if str(payload.get("video_id", video_id)) != video_id:
        raise ValueError("Payload video_id does not match URL video_id")
    output_path = output_root / video_id / FEEDBACK_FILENAME
    saved_payload = dict(payload)
    saved_payload["video_id"] = video_id
    saved_payload["saved_at"] = now_iso()
    write_json(output_path, saved_payload)
    return output_path


class AlgorithmReviewHandler(SimpleHTTPRequestHandler):
    data_root: Path
    output_root: Path

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            self._send_file(TOOL_DIR / "index.html")
            return
        if path == "/review_tool.js":
            self._send_file(TOOL_DIR / "review_tool.js")
            return
        if path == "/api/episodes":
            self._send_json(build_episode_index(data_root=self.data_root, output_root=self.output_root))
            return
        api_match = re.fullmatch(r"/api/episodes/([^/]+)/([^/]+)", path)
        if api_match:
            video_id, resource = api_match.groups()
            self._send_episode_resource(video_id, resource)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        api_match = re.fullmatch(r"/api/episodes/([^/]+)/feedback", path)
        if not api_match:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        video_id = api_match.group(1)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Feedback payload must be a JSON object")
            output_path = save_feedback_payload(video_id=video_id, output_root=self.output_root, payload=payload)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"ok": True, "feedback_path": str(output_path)})

    def _episode_for_id(self, video_id: str) -> dict[str, Any] | None:
        if not is_valid_video_id(video_id):
            return None
        index = build_episode_index(data_root=self.data_root, output_root=self.output_root)
        return next((episode for episode in index["episodes"] if episode["video_id"] == video_id), None)

    def _send_episode_resource(self, video_id: str, resource: str) -> None:
        episode = self._episode_for_id(video_id)
        if episode is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Episode not found")
            return
        episode_dir = Path(str(episode["episode_dir"]))
        if resource == "video":
            self._send_file(episode_dir / "video.mp4", allow_range=True)
            return
        if resource == "subtitle":
            self._send_file(episode_dir / "video.srt")
            return
        if resource == "danmaku":
            self._send_json(read_json(episode_dir / "douyin.json") or {})
            return
        if resource == "scene-detection":
            self._send_json(read_json(episode_dir / "scene_detection.json") or {})
            return
        if resource == "algorithm-output":
            output_type, output_path = resolve_algorithm_output(video_id, self.output_root)
            if output_path is None:
                self._send_json({"video_id": video_id, "output_type": None})
                return
            payload = read_json(output_path)
            if isinstance(payload, dict):
                payload = {**payload, "_review_output_type": output_type, "_review_output_path": str(output_path)}
            self._send_json(payload or {})
            return
        if resource == "feedback":
            self._send_json(read_json(self.output_root / video_id / FEEDBACK_FILENAME) or {"video_id": video_id})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Resource not found")

    def _send_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, *, allow_range: bool = False) -> None:
        if not path.exists() or path.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        if allow_range and self.headers.get("Range"):
            byte_range = self._parse_single_range(self.headers.get("Range", ""), path.stat().st_size)
            if byte_range is None:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            self._send_file_range(path, byte_range)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Length", str(len(body)))
        if allow_range:
            self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(body)

    def _send_file_range(self, path: Path, byte_range: tuple[int, int]) -> None:
        start, end = byte_range
        content_length = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            body = handle.read(content_length)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{path.stat().st_size}")
        self.send_header("Content-Length", str(content_length))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _parse_single_range(value: str, file_size: int) -> tuple[int, int] | None:
        if not value.startswith("bytes="):
            return None
        range_value = value.removeprefix("bytes=").split(",", 1)[0].strip()
        if "-" not in range_value:
            return None
        start_text, end_text = range_value.split("-", 1)
        try:
            if start_text == "":
                suffix_length = int(end_text)
                if suffix_length <= 0:
                    return None
                start = max(0, file_size - suffix_length)
                end = file_size - 1
            else:
                start = int(start_text)
                end = int(end_text) if end_text else file_size - 1
        except ValueError:
            return None
        if start < 0 or start >= file_size or end < start:
            return None
        return start, min(end, file_size - 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the DramePulse algorithm review tool.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    handler = type(
        "ConfiguredAlgorithmReviewHandler",
        (AlgorithmReviewHandler,),
        {"data_root": args.data_root, "output_root": args.output_root},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving algorithm review tool on http://{args.host}:{args.port}/")
    print(f"Data root: {args.data_root}")
    print(f"Output root: {args.output_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

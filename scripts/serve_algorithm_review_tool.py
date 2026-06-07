from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence
from urllib.parse import unquote, urlparse

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.algorithm_danmaku_csv import index_danmaku_csv_episodes, load_danmaku_csv_items


DEFAULT_DATA_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")
DEFAULT_OUTPUT_ROOT = Path("output")
DEFAULT_ANNOTATION_DIR = Path("data/annotations/expression_trigger_gold")
TOOL_DIR = Path(__file__).resolve().parents[1] / "apps" / "algorithm-review-tool"
ANNOTATION_TOOL_DIR = Path(__file__).resolve().parents[1] / "apps" / "annotation-tool"
SUBTITLE_DENSITY_TOOL_DIR = Path(__file__).resolve().parents[1] / "apps" / "subtitle-density-tool"
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


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
        ("expression_triggers", output_root / video_id / "expression_triggers.json"),
        ("highlight_recognition", output_root / video_id / "highlight_recognition.json"),
        ("highlight_candidates", output_root / video_id / "highlight_candidates.json"),
    )
    for output_type, path in candidates:
        if path.exists():
            return output_type, path
    return None, None


def resolve_subtitle_density_output(video_id: str, output_root: Path) -> Path | None:
    candidates = (
        output_root / video_id / "subtitle_dialogue_density.json",
        output_root / "subtitle_dialogue_density" / video_id / "subtitle_dialogue_density.json",
        output_root.parent / "subtitle_dialogue_density" / video_id / "subtitle_dialogue_density.json",
    )
    for path in candidates:
        if path.exists():
            return path
    return None


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _annotation_time(item: dict[str, Any]) -> float | None:
    for key in ("payoff_time", "cue_time"):
        try:
            return _round_time(float(item[key]))
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _annotation_window(item: dict[str, Any]) -> dict[str, float] | None:
    window = item.get("payoff_window")
    if not isinstance(window, dict):
        return None
    try:
        start_time = _round_time(float(window["start_time"]))
        end_time = _round_time(float(window["end_time"]))
    except (KeyError, TypeError, ValueError):
        return None
    if start_time < 0 or end_time < start_time:
        return None
    return {"start_time": start_time, "end_time": end_time}


def load_gold_annotation_payload(*, video_id: str, annotation_dir: Path) -> dict[str, Any]:
    annotation_path = annotation_dir / f"{video_id}.annotation.json"
    payload = read_json(annotation_path)
    if not isinstance(payload, dict):
        return {"video_id": video_id, "annotation_count": 0, "annotations": []}
    raw_annotations = payload.get("annotations")
    if not isinstance(raw_annotations, list):
        return {"video_id": video_id, "annotation_count": 0, "annotations": []}
    annotations: list[dict[str, Any]] = []
    for index, item in enumerate(raw_annotations, start=1):
        if not isinstance(item, dict):
            continue
        annotation_time = _annotation_time(item)
        if annotation_time is None or annotation_time < 0:
            continue
        annotations.append(
            {
                "annotation_id": str(item.get("annotation_id") or f"gold_{video_id}_{index:03d}"),
                "cue_time": annotation_time,
                "payoff_time": annotation_time,
                "primary_expression": str(item.get("primary_expression") or item.get("expression_type") or "").strip(),
                "reason": str(item.get("reason") or "").strip(),
                "payoff_window": _annotation_window(item),
            }
        )
    annotations = sorted(annotations, key=lambda item: (float(item["cue_time"]), str(item["annotation_id"])))
    return {
        "video_id": video_id,
        "annotation_count": len(annotations),
        "annotations": annotations,
        "_review_output_type": "expression_trigger_gold",
        "_review_output_path": str(annotation_path) if annotation_path.exists() else None,
    }


def load_subtitle_density_payload(*, video_id: str, output_root: Path) -> dict[str, Any]:
    output_path = resolve_subtitle_density_output(video_id, output_root)
    if output_path is None:
        return {"video_id": video_id, "output_type": None, "density_windows": [], "dialogue_ranges": [], "silent_ranges": []}
    payload = read_json(output_path)
    if isinstance(payload, dict):
        return {**payload, "_review_output_type": "subtitle_dialogue_density", "_review_output_path": str(output_path)}
    return {"video_id": video_id, "output_type": None, "density_windows": [], "dialogue_ranges": [], "silent_ranges": []}


def resolve_danmaku_source(
    *,
    episode_dir: Path,
    series_id: str,
    episode_id: str,
    csv_episode_paths: dict[tuple[str, str], Path],
) -> tuple[str | None, Path | None]:
    csv_path = csv_episode_paths.get((series_id, episode_id))
    if csv_path is not None:
        return "csv", csv_path
    douyin_path = episode_dir / "douyin.json"
    if douyin_path.exists():
        return "douyin_json", douyin_path
    return None, None


def load_episode_danmaku_payload(*, data_root: Path, episode_dir: Path, series_id: str, episode_id: str) -> dict[str, Any]:
    csv_items = load_danmaku_csv_items(data_root, series_id=series_id, episode_id=episode_id)
    if csv_items:
        return {"source": "csv", "count": len(csv_items), "items": csv_items}
    payload = read_json(episode_dir / "douyin.json")
    if isinstance(payload, dict):
        return {**payload, "source": "douyin_json"}
    return {"source": None, "count": 0, "items": []}


def build_episode_index(*, data_root: Path, output_root: Path, annotation_dir: Path = DEFAULT_ANNOTATION_DIR) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    csv_episode_paths = index_danmaku_csv_episodes(data_root)
    for video_path in sorted(data_root.glob("*/ep*/video.mp4")):
        episode_dir = video_path.parent
        series_id = episode_dir.parent.name
        episode_id = episode_dir.name
        video_id = f"{series_id}_{episode_id}"
        output_type, algorithm_output_path = resolve_algorithm_output(video_id, output_root)
        gold_payload = load_gold_annotation_payload(video_id=video_id, annotation_dir=annotation_dir)
        subtitle_density_path = resolve_subtitle_density_output(video_id, output_root)
        danmaku_source, danmaku_path = resolve_danmaku_source(
            episode_dir=episode_dir,
            series_id=series_id,
            episode_id=episode_id,
            csv_episode_paths=csv_episode_paths,
        )
        episodes.append(
            {
                "video_id": video_id,
                "series_id": series_id,
                "episode_id": episode_id,
                "title": extract_title(episode_dir, series_id=series_id, episode_id=episode_id),
                "episode_dir": str(episode_dir),
                "video_path": str(video_path),
                "subtitle_path": str(episode_dir / "video.srt") if (episode_dir / "video.srt").exists() else None,
                "danmaku_path": str(danmaku_path) if danmaku_path else None,
                "danmaku_source": danmaku_source,
                "scene_detection_path": str(episode_dir / "scene_detection.json")
                if (episode_dir / "scene_detection.json").exists()
                else None,
                "has_subtitle": (episode_dir / "video.srt").exists(),
                "has_danmaku": danmaku_path is not None,
                "has_scene_detection": (episode_dir / "scene_detection.json").exists(),
                "algorithm_output_type": output_type,
                "algorithm_output_path": str(algorithm_output_path) if algorithm_output_path else None,
                "gold_annotation_path": gold_payload.get("_review_output_path"),
                "gold_annotation_count": gold_payload["annotation_count"],
                "has_gold_annotations": int(gold_payload["annotation_count"]) > 0,
                "subtitle_density_path": str(subtitle_density_path) if subtitle_density_path else None,
                "has_subtitle_density": subtitle_density_path is not None,
            }
        )
    return {
        "dataset_root": str(data_root),
        "output_root": str(output_root),
        "episodes": episodes,
    }


class AlgorithmReviewHandler(SimpleHTTPRequestHandler):
    data_root: Path
    output_root: Path
    annotation_dir: Path

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            self._send_file(TOOL_DIR / "index.html")
            return
        if path == "/review_tool.js":
            self._send_file(TOOL_DIR / "review_tool.js")
            return
        if path in {"/apps/annotation-tool", "/apps/annotation-tool/"}:
            self._send_file(ANNOTATION_TOOL_DIR / "index.html")
            return
        if path == "/apps/annotation-tool/annotation_tool.js":
            self._send_file(ANNOTATION_TOOL_DIR / "annotation_tool.js")
            return
        if path in {"/apps/subtitle-density-tool", "/apps/subtitle-density-tool/"}:
            self._send_file(SUBTITLE_DENSITY_TOOL_DIR / "index.html")
            return
        if path == "/apps/subtitle-density-tool/subtitle_density_tool.js":
            self._send_file(SUBTITLE_DENSITY_TOOL_DIR / "subtitle_density_tool.js")
            return
        if path == "/api/episodes":
            self._send_json(build_episode_index(data_root=self.data_root, output_root=self.output_root, annotation_dir=self.annotation_dir))
            return
        api_match = re.fullmatch(r"/api/episodes/([^/]+)/([^/]+)", path)
        if api_match:
            video_id, resource = api_match.groups()
            self._send_episode_resource(video_id, resource)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _episode_for_id(self, video_id: str) -> dict[str, Any] | None:
        if not is_valid_video_id(video_id):
            return None
        index = build_episode_index(data_root=self.data_root, output_root=self.output_root, annotation_dir=self.annotation_dir)
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
            self._send_json(
                load_episode_danmaku_payload(
                    data_root=self.data_root,
                    episode_dir=episode_dir,
                    series_id=str(episode["series_id"]),
                    episode_id=str(episode["episode_id"]),
                )
            )
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
        if resource == "gold-annotations":
            self._send_json(load_gold_annotation_payload(video_id=video_id, annotation_dir=self.annotation_dir))
            return
        if resource == "subtitle-density":
            self._send_json(load_subtitle_density_payload(video_id=video_id, output_root=self.output_root))
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Resource not found")

    def _send_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._write_response_body(body)

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
        self._write_response_body(body)

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
        self._write_response_body(body)

    def _write_response_body(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

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
    parser.add_argument("--annotation-dir", type=Path, default=DEFAULT_ANNOTATION_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    handler = type(
        "ConfiguredAlgorithmReviewHandler",
        (AlgorithmReviewHandler,),
        {"data_root": args.data_root, "output_root": args.output_root, "annotation_dir": args.annotation_dir},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving algorithm review tool on http://{args.host}:{args.port}/")
    print(f"Data root: {args.data_root}")
    print(f"Output root: {args.output_root}")
    print(f"Annotation dir: {args.annotation_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

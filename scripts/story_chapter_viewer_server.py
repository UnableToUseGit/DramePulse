from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
from typing import Any, Sequence
from urllib.parse import unquote, urlparse


DEFAULT_DATASET_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")
STATIC_ROOT = Path(__file__).resolve().parents[1] / "apps" / "story-chapter-viewer"


@dataclass(frozen=True)
class EpisodeIndexEntry:
    episode_id: str
    video_id: str
    series_slug: str
    episode_slug: str
    episode_dir: Path
    video_path: Path
    scene_path: Path
    chapter_path: Path | None
    has_chapters: bool
    duration: float | None
    scene_count: int


def make_episode_id(series_slug: str, episode_slug: str) -> str:
    return f"{series_slug}_{episode_slug}"


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _find_chapter_path(
    *,
    episode_dir: Path,
    video_id: str,
    episode_id: str,
    chapter_output_root: Path | None,
) -> Path | None:
    candidates = [episode_dir / "story_chapters.json"]
    if chapter_output_root is not None:
        candidates.append(chapter_output_root / video_id / "story_chapters.json")
        if episode_id != video_id:
            candidates.append(chapter_output_root / episode_id / "story_chapters.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def discover_episodes(dataset_root: Path, chapter_output_root: Path | None = None) -> list[EpisodeIndexEntry]:
    entries: list[EpisodeIndexEntry] = []
    if not dataset_root.exists():
        raise FileNotFoundError(dataset_root)

    for series_dir in sorted(path for path in dataset_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
        for episode_dir in sorted(path for path in series_dir.iterdir() if path.is_dir() and not path.name.startswith(".")):
            video_path = episode_dir / "video.mp4"
            scene_path = episode_dir / "scene_detection.json"
            if not video_path.exists() or not scene_path.exists():
                continue

            scene_payload = _safe_read_json(scene_path)
            episode_id = make_episode_id(series_dir.name, episode_dir.name)
            video_id = str(scene_payload.get("video_id") or episode_id)
            scenes = scene_payload.get("scenes") if isinstance(scene_payload.get("scenes"), list) else []
            duration = None
            if scenes:
                end_times = [
                    float(scene.get("end_time"))
                    for scene in scenes
                    if isinstance(scene, dict) and isinstance(scene.get("end_time"), int | float)
                ]
                duration = max(end_times) if end_times else None
            chapter_path = _find_chapter_path(
                episode_dir=episode_dir,
                video_id=video_id,
                episode_id=episode_id,
                chapter_output_root=chapter_output_root,
            )
            entries.append(
                EpisodeIndexEntry(
                    episode_id=episode_id,
                    video_id=video_id,
                    series_slug=series_dir.name,
                    episode_slug=episode_dir.name,
                    episode_dir=episode_dir,
                    video_path=video_path,
                    scene_path=scene_path,
                    chapter_path=chapter_path,
                    has_chapters=chapter_path is not None,
                    duration=duration,
                    scene_count=len(scenes),
                )
            )
    return entries


def _normalize_scene(scene: dict[str, Any], index: int) -> dict[str, Any] | None:
    try:
        start_time = float(scene["start_time"])
        end_time = float(scene["end_time"])
    except (KeyError, TypeError, ValueError):
        return None
    if end_time <= start_time:
        return None
    return {
        "scene_id": str(scene.get("scene_id") or f"s_{index:03d}"),
        "index": int(scene.get("index") or index),
        "start_time": round(start_time, 3),
        "end_time": round(end_time, 3),
        "duration": round(end_time - start_time, 3),
    }


def _normalize_chapter(chapter: dict[str, Any], index: int) -> dict[str, Any] | None:
    try:
        start_time = float(chapter["start_time"])
        end_time = float(chapter["end_time"])
    except (KeyError, TypeError, ValueError):
        return None
    if end_time <= start_time:
        return None
    return {
        "chapter_id": str(chapter.get("chapter_id") or f"ch_{index:03d}"),
        "start_time": round(start_time, 3),
        "end_time": round(end_time, 3),
        "title": str(chapter.get("title") or f"章节 {index}"),
        "summary": str(chapter.get("summary") or ""),
        "importance": float(chapter.get("importance") or 0.0),
    }


def load_episode_detail(entry: EpisodeIndexEntry) -> dict[str, Any]:
    scene_payload = _safe_read_json(entry.scene_path)
    raw_scenes = scene_payload.get("scenes") if isinstance(scene_payload.get("scenes"), list) else []
    scenes = [
        normalized
        for index, scene in enumerate(raw_scenes, start=1)
        if isinstance(scene, dict)
        if (normalized := _normalize_scene(scene, index)) is not None
    ]

    chapters: list[dict[str, Any]] = []
    warnings: list[str] = []
    if entry.chapter_path is not None:
        chapter_payload = _safe_read_json(entry.chapter_path)
        raw_chapters = chapter_payload.get("story_chapters")
        if isinstance(raw_chapters, list):
            chapters = [
                normalized
                for index, chapter in enumerate(raw_chapters, start=1)
                if isinstance(chapter, dict)
                if (normalized := _normalize_chapter(chapter, index)) is not None
            ]
        raw_warnings = chapter_payload.get("warnings")
        if isinstance(raw_warnings, list):
            warnings = [str(warning) for warning in raw_warnings]

    duration_candidates = [entry.duration or 0.0]
    duration_candidates.extend(scene["end_time"] for scene in scenes)
    duration_candidates.extend(chapter["end_time"] for chapter in chapters)

    return {
        "episode_id": entry.episode_id,
        "video_id": entry.video_id,
        "series_slug": entry.series_slug,
        "episode_slug": entry.episode_slug,
        "media_url": f"/media/{entry.episode_id}/video.mp4",
        "duration": round(max(duration_candidates), 3),
        "scene_count": len(scenes),
        "chapter_count": len(chapters),
        "has_chapters": entry.has_chapters,
        "chapter_source": str(entry.chapter_path) if entry.chapter_path is not None else None,
        "scenes": scenes,
        "chapters": chapters,
        "warnings": warnings,
    }


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def write_chunk_safely(writer: Any, chunk: bytes) -> bool:
    try:
        writer.write(chunk)
    except (BrokenPipeError, ConnectionResetError):
        return False
    return True


class StoryChapterViewerHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args,
        episodes: Sequence[EpisodeIndexEntry],
        static_root: Path,
        **kwargs,
    ) -> None:
        self.episodes_by_id = {entry.episode_id: entry for entry in episodes}
        self.static_root = static_root
        super().__init__(*args, directory=str(static_root), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        self._handle_request(include_body=True)

    def do_HEAD(self) -> None:
        self._handle_request(include_body=False)

    def _handle_request(self, *, include_body: bool) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/episodes":
            self._send_json([self._episode_summary(entry) for entry in self.episodes_by_id.values()])
            return
        match = re.fullmatch(r"/api/episodes/([^/]+)", path)
        if match:
            self._send_episode_detail(match.group(1))
            return
        match = re.fullmatch(r"/media/([^/]+)/video\.mp4", path)
        if match:
            self._send_video(match.group(1), include_body=include_body)
            return
        if path == "/":
            self.path = "/index.html"
        if include_body:
            super().do_GET()
        else:
            super().do_HEAD()

    def _episode_summary(self, entry: EpisodeIndexEntry) -> dict[str, Any]:
        return {
            "episode_id": entry.episode_id,
            "video_id": entry.video_id,
            "series_slug": entry.series_slug,
            "episode_slug": entry.episode_slug,
            "duration": entry.duration,
            "scene_count": entry.scene_count,
            "has_chapters": entry.has_chapters,
        }

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_episode_detail(self, episode_id: str) -> None:
        entry = self.episodes_by_id.get(episode_id)
        if entry is None:
            self._send_json({"error": "episode not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(load_episode_detail(entry))

    def _send_video(self, episode_id: str, *, include_body: bool) -> None:
        entry = self.episodes_by_id.get(episode_id)
        if entry is None or not entry.video_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "video not found")
            return
        file_size = entry.video_path.stat().st_size
        content_type = mimetypes.guess_type(entry.video_path.name)[0] or "video/mp4"
        range_header = self.headers.get("Range")
        start = 0
        end = file_size - 1
        status = HTTPStatus.OK
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if match:
                if match.group(1):
                    start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
                if not match.group(1) and match.group(2):
                    suffix_length = int(match.group(2))
                    start = max(0, file_size - suffix_length)
                    end = file_size - 1
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
                status = HTTPStatus.PARTIAL_CONTENT
        content_length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        if not include_body:
            return
        with entry.video_path.open("rb") as file:
            file.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk = file.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                if not write_chunk_safely(self.wfile, chunk):
                    break
                remaining -= len(chunk)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve a local read-only Story Chapter validation viewer.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--chapter-output-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    episodes = discover_episodes(args.dataset_root, chapter_output_root=args.chapter_output_root)
    handler = partial(StoryChapterViewerHandler, episodes=episodes, static_root=STATIC_ROOT)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Story Chapter Viewer: {url}")
    print(f"Dataset root: {args.dataset_root}")
    print(f"Episodes indexed: {len(episodes)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import re
import sys
from collections.abc import Sequence
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DEFAULT_DATA_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")
DEFAULT_PLAN_ROOT = Path("output/interaction_plan")
DEFAULT_CURATED_ROOT = Path("output/interaction_plan_curated")
TOOL_DIR = Path(__file__).resolve().parents[1] / "apps" / "interaction-plan-editor"
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


def _round_time(value: Any) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return 0.0


def _episode_no(video_id: str) -> int:
    match = re.search(r"_ep(\d+)$", video_id)
    return int(match.group(1)) if match else 0


def extract_title(episode_dir: Path, *, series_id: str, episode_id: str) -> str:
    payload = read_json(episode_dir / "douyin.json")
    if isinstance(payload, dict):
        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata.get("title"):
            return str(metadata["title"])
    return f"{series_id} {episode_id}"


def discover_interaction_plan_paths(video_id: str, plan_root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    direct_path = plan_root / video_id / "interaction_plan.json"
    if direct_path.exists():
        candidates.append({"source": "root", "path": direct_path})
    if plan_root.exists():
        for source_dir in sorted(path for path in plan_root.iterdir() if path.is_dir()):
            plan_path = source_dir / video_id / "interaction_plan.json"
            if plan_path.exists():
                candidates.append({"source": source_dir.name, "path": plan_path})
    return candidates


def curated_plan_path(video_id: str, curated_root: Path) -> Path:
    return curated_root / video_id / "interaction_plan.json"


def edit_log_path(video_id: str, curated_root: Path) -> Path:
    return curated_root / video_id / "interaction_plan.edits.json"


def resolve_interaction_plan_path(video_id: str, plan_root: Path) -> Path | None:
    sources = discover_interaction_plan_paths(video_id, plan_root)
    return sources[0]["path"] if sources else None


def _load_plan(path: Path | None) -> list[dict[str, Any]]:
    payload = read_json(path) if path is not None else None
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _normalize_plan(
    plan: list[dict[str, Any]],
    *,
    plan_source: str | None = None,
    plan_source_path: Path | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(plan, start=1):
        if not isinstance(item, dict):
            continue
        current = dict(item)
        video_id = str(current.get("video_id") or "").strip()
        if not video_id:
            continue
        interaction_id = str(current.get("interaction_id") or f"ip_{video_id}_{index:03d}")
        trigger_time = max(0.0, _round_time(current.get("trigger_time")))
        duration_sec = max(0.0, _round_time(current.get("duration_sec", 5.0)))
        current["interaction_id"] = interaction_id
        current["video_id"] = video_id
        current["series_id"] = str(current.get("series_id") or video_id.rsplit("_ep", 1)[0])
        current["episode_no"] = int(current.get("episode_no") or _episode_no(video_id))
        current["interaction_mode"] = str(current.get("interaction_mode") or "emotional_button")
        current["trigger_time"] = trigger_time
        current["duration_sec"] = duration_sec
        current["expire_time"] = _round_time(trigger_time + duration_sec)
        content = current.get("content")
        current["content"] = dict(content) if isinstance(content, dict) else {}
        if plan_source is not None:
            current["_plan_source"] = plan_source
        if plan_source_path is not None:
            current["_plan_source_path"] = str(plan_source_path)
        normalized.append(current)
    return sorted(normalized, key=lambda item: (float(item["trigger_time"]), str(item["interaction_id"])))


def _load_source_plan(source: dict[str, Any]) -> list[dict[str, Any]]:
    path = source["path"]
    return _normalize_plan(_load_plan(path), plan_source=str(source["source"]), plan_source_path=path)


def load_original_interaction_plan(video_id: str, plan_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = discover_interaction_plan_paths(video_id, plan_root)
    plan: list[dict[str, Any]] = []
    for source in sources:
        plan.extend(_load_source_plan(source))
    plan = sorted(plan, key=lambda item: (float(item["trigger_time"]), str(item["interaction_id"])))
    return plan, sources


def _strip_private_fields(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in plan:
        cleaned_item = {key: value for key, value in item.items() if not str(key).startswith("_")}
        cleaned.append(cleaned_item)
    return cleaned


def _editable_diff_fields(item: dict[str, Any]) -> dict[str, Any]:
    content = item.get("content")
    return {
        "interaction_mode": item.get("interaction_mode"),
        "trigger_time": item.get("trigger_time"),
        "duration_sec": item.get("duration_sec"),
        "content": dict(content) if isinstance(content, dict) else {},
    }


def _flatten_editable_fields(item: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "interaction_mode": item.get("interaction_mode"),
        "trigger_time": item.get("trigger_time"),
        "duration_sec": item.get("duration_sec"),
    }
    content = item.get("content")
    if isinstance(content, dict):
        for key, value in sorted(content.items()):
            flat[f"content.{key}"] = value
    return flat


def build_edit_log(
    *,
    video_id: str,
    original_plan: list[dict[str, Any]],
    curated_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    original_by_id = {str(item.get("interaction_id")): _editable_diff_fields(item) for item in original_plan}
    curated_by_id = {str(item.get("interaction_id")): _editable_diff_fields(item) for item in curated_plan}
    edits: list[dict[str, Any]] = []
    for interaction_id in sorted(set(original_by_id) - set(curated_by_id)):
        edits.append(
            {
                "interaction_id": interaction_id,
                "action": "deleted",
                "field": "__interaction",
                "before": original_by_id[interaction_id],
                "after": None,
            }
        )
    for interaction_id in sorted(set(curated_by_id) - set(original_by_id)):
        edits.append(
            {
                "interaction_id": interaction_id,
                "action": "added",
                "field": "__interaction",
                "before": None,
                "after": curated_by_id[interaction_id],
            }
        )
    for item in curated_plan:
        interaction_id = str(item.get("interaction_id") or "")
        if interaction_id not in original_by_id:
            continue
        before = original_by_id.get(interaction_id, {})
        before_flat = _flatten_editable_fields(before)
        after_flat = _flatten_editable_fields(_editable_diff_fields(item))
        for field in sorted(set(before_flat) | set(after_flat)):
            before_value = before_flat.get(field)
            after_value = after_flat.get(field)
            if before_value == after_value:
                continue
            edits.append(
                {
                    "interaction_id": interaction_id,
                    "action": "updated",
                    "field": field,
                    "before": before_value,
                    "after": after_value,
                }
            )
    return {
        "video_id": video_id,
        "created_at": now_iso(),
        "edit_count": len(edits),
        "edits": edits,
    }


def load_interaction_plan_payload(*, video_id: str, plan_root: Path, curated_root: Path) -> dict[str, Any]:
    if not is_valid_video_id(video_id):
        return {"video_id": video_id, "error": "invalid video_id", "original_plan": [], "curated_plan": [], "active_plan": []}
    original_plan, sources = load_original_interaction_plan(video_id, plan_root)
    curated_path = curated_plan_path(video_id, curated_root)
    curated_plan = _normalize_plan(_load_plan(curated_path))
    active_plan = curated_plan if curated_plan else original_plan
    return {
        "video_id": video_id,
        "original_plan_path": str(sources[0]["path"]) if sources else None,
        "original_plan_paths": [str(source["path"]) for source in sources],
        "source_plans": [{"source": str(source["source"]), "path": str(source["path"])} for source in sources],
        "curated_plan_path": str(curated_path) if curated_path.exists() else None,
        "edit_log_path": str(edit_log_path(video_id, curated_root)) if edit_log_path(video_id, curated_root).exists() else None,
        "has_original_plan": bool(original_plan),
        "has_curated_plan": bool(curated_plan),
        "original_plan": original_plan,
        "curated_plan": curated_plan,
        "active_plan": active_plan,
    }


def write_curated_interaction_plan(
    *,
    video_id: str,
    plan: list[dict[str, Any]],
    plan_root: Path,
    curated_root: Path,
) -> dict[str, Path]:
    if not is_valid_video_id(video_id):
        raise ValueError(f"Invalid video_id: {video_id}")
    original_plan, sources = load_original_interaction_plan(video_id, plan_root)
    curated_plan = _strip_private_fields(_normalize_plan(plan))
    output_path = curated_plan_path(video_id, curated_root)
    log_path = edit_log_path(video_id, curated_root)
    write_json(output_path, curated_plan)
    edit_log = build_edit_log(video_id=video_id, original_plan=original_plan, curated_plan=curated_plan)
    edit_log["source_plans"] = [{"source": str(source["source"]), "path": str(source["path"])} for source in sources]
    write_json(log_path, edit_log)
    return {"curated_plan_path": output_path, "edit_log_path": log_path}


def build_episode_index(*, data_root: Path, plan_root: Path, curated_root: Path) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    for video_path in sorted(data_root.glob("*/ep*/video.mp4")):
        episode_dir = video_path.parent
        series_id = episode_dir.parent.name
        episode_id = episode_dir.name
        video_id = f"{series_id}_{episode_id}"
        plan_sources = discover_interaction_plan_paths(video_id, plan_root)
        curated_path = curated_plan_path(video_id, curated_root)
        episodes.append(
            {
                "video_id": video_id,
                "series_id": series_id,
                "episode_id": episode_id,
                "episode_no": _episode_no(video_id),
                "title": extract_title(episode_dir, series_id=series_id, episode_id=episode_id),
                "episode_dir": str(episode_dir),
                "video_path": str(video_path),
                "has_interaction_plan": bool(plan_sources),
                "interaction_plan_count": len(plan_sources),
                "interaction_plan_path": str(plan_sources[0]["path"]) if plan_sources else None,
                "interaction_plan_paths": [str(source["path"]) for source in plan_sources],
                "interaction_plan_sources": [str(source["source"]) for source in plan_sources],
                "has_curated_plan": curated_path.exists(),
                "curated_plan_path": str(curated_path) if curated_path.exists() else None,
            }
        )
    return {
        "data_root": str(data_root),
        "plan_root": str(plan_root),
        "curated_root": str(curated_root),
        "episodes": episodes,
    }


class InteractionPlanEditorHandler(SimpleHTTPRequestHandler):
    data_root: Path
    plan_root: Path
    curated_root: Path

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            self._send_file(TOOL_DIR / "index.html")
            return
        if path == "/editor.js":
            self._send_file(TOOL_DIR / "editor.js")
            return
        if path == "/styles.css":
            self._send_file(TOOL_DIR / "styles.css")
            return
        if path == "/api/episodes":
            self._send_json(build_episode_index(data_root=self.data_root, plan_root=self.plan_root, curated_root=self.curated_root))
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
        api_match = re.fullmatch(r"/api/episodes/([^/]+)/interaction-plan", path)
        if not api_match:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        video_id = api_match.group(1)
        if not is_valid_video_id(video_id):
            self._send_json({"error": "Invalid video_id"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        try:
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return
        plan = payload.get("interaction_plan") if isinstance(payload, dict) else None
        if not isinstance(plan, list):
            self._send_json({"error": "interaction_plan must be a list"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            result = write_curated_interaction_plan(video_id=video_id, plan=plan, plan_root=self.plan_root, curated_root=self.curated_root)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(
            {
                "video_id": video_id,
                "curated_plan_path": str(result["curated_plan_path"]),
                "edit_log_path": str(result["edit_log_path"]),
            }
        )

    def _send_episode_resource(self, video_id: str, resource: str) -> None:
        if not is_valid_video_id(video_id):
            self.send_error(HTTPStatus.NOT_FOUND, "Episode not found")
            return
        episode = next(
            (
                item
                for item in build_episode_index(data_root=self.data_root, plan_root=self.plan_root, curated_root=self.curated_root)["episodes"]
                if item["video_id"] == video_id
            ),
            None,
        )
        if episode is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Episode not found")
            return
        if resource == "video":
            self._send_file(Path(str(episode["video_path"])), allow_range=True)
            return
        if resource == "interaction-plan":
            self._send_json(load_interaction_plan_payload(video_id=video_id, plan_root=self.plan_root, curated_root=self.curated_root))
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
        with path.open("rb") as handle:
            handle.seek(start)
            body = handle.read(end - start + 1)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{path.stat().st_size}")
        self.send_header("Content-Length", str(len(body)))
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
    parser = argparse.ArgumentParser(description="Serve the DramePulse interaction plan editor.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8783)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--plan-root", type=Path, default=DEFAULT_PLAN_ROOT)
    parser.add_argument("--curated-root", type=Path, default=DEFAULT_CURATED_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    handler = type(
        "ConfiguredInteractionPlanEditorHandler",
        (InteractionPlanEditorHandler,),
        {"data_root": args.data_root, "plan_root": args.plan_root, "curated_root": args.curated_root},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving interaction plan editor on http://{args.host}:{args.port}/")
    print(f"Data root: {args.data_root}")
    print(f"Plan root: {args.plan_root}")
    print(f"Curated root: {args.curated_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

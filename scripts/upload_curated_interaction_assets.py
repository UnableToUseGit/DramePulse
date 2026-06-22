from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


DEFAULT_BACKEND_URL = "http://39.96.219.88:8000/"
DEFAULT_CURATED_ROOT = Path("output/interaction_plan_curated")
DEFAULT_COOKIES_FILE = Path("/Users/qinminghao/Desktop/cookies.txt")
INTERACTION_PLAN_FILENAME = "interaction_plan.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _round_time(value: Any) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return 0.0


def _episode_no(video_id: str) -> int:
    marker = "_ep"
    if marker not in video_id:
        return 0
    suffix = video_id.rsplit(marker, 1)[1]
    return int(suffix) if suffix.isdigit() else 0


def _series_id_from_video_id(video_id: str) -> str:
    marker_index = video_id.rfind("_ep")
    return video_id[:marker_index] if marker_index > 0 else video_id


def discover_video_ids(curated_root: Path, *, video_ids: Sequence[str] | None = None) -> list[str]:
    if video_ids:
        return sorted(set(video_ids))
    if not curated_root.exists():
        raise FileNotFoundError(curated_root)
    return sorted(path.parent.name for path in curated_root.glob(f"*/{INTERACTION_PLAN_FILENAME}"))


def load_curated_plan(curated_root: Path, video_id: str) -> list[dict[str, Any]]:
    path = curated_root / video_id / INTERACTION_PLAN_FILENAME
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [item for item in payload if isinstance(item, dict)]


def normalize_interaction_item(item: dict[str, Any]) -> dict[str, Any]:
    trigger_time = _round_time(item.get("trigger_time"))
    duration_sec = _round_time(item.get("duration_sec"))
    expire_time = _round_time(item.get("expire_time", trigger_time + duration_sec))
    content = item.get("content")
    return {
        "interaction_id": str(item.get("interaction_id") or ""),
        "trigger_time": max(0.0, trigger_time),
        "expire_time": max(0.0, expire_time),
        "duration_sec": max(0.0, duration_sec),
        "content": dict(content) if isinstance(content, dict) else {},
        "status": str(item.get("status") or "active"),
    }


def build_upload_payloads_for_video(
    *,
    video_id: str,
    plan: Sequence[dict[str, Any]],
    replace_existing: bool = True,
    canonical_series_id: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    series_ids: dict[str, str] = {}
    episode_numbers: dict[str, int] = {}
    for item in plan:
        interaction_mode = str(item.get("interaction_mode") or "").strip()
        if not interaction_mode:
            raise ValueError(f"{video_id}: item {item.get('interaction_id')} missing interaction_mode")
        normalized_item = normalize_interaction_item(item)
        if not normalized_item["interaction_id"]:
            raise ValueError(f"{video_id}: item missing interaction_id")
        grouped[interaction_mode].append(normalized_item)
        series_ids.setdefault(interaction_mode, str(item.get("series_id") or _series_id_from_video_id(video_id)))
        episode_numbers.setdefault(interaction_mode, int(item.get("episode_no") or _episode_no(video_id)))

    payloads: list[dict[str, Any]] = []
    for interaction_mode in sorted(grouped):
        source_series_id = series_ids[interaction_mode]
        payloads.append(
            {
                "interaction_mode": interaction_mode,
                "items": sorted(grouped[interaction_mode], key=lambda current: (current["trigger_time"], current["interaction_id"])),
                "replace_existing": replace_existing,
                "source_video_id": video_id,
                "source_series_id": source_series_id,
                "canonical_series_id": canonical_series_id or source_series_id,
                "episode_no": episode_numbers[interaction_mode],
                "asset_id": f"ia_{video_id}_{interaction_mode}",
            }
        )
    return payloads


def build_upload_url(backend_url: str, video_id: str) -> str:
    base_url = backend_url.rstrip("/") + "/"
    path = f"api/admin/videos/{quote(video_id, safe='')}/interaction-assets"
    return urljoin(base_url, path)


def _strip_cookie_value_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_cookie_header(cookies_file: Path | None, *, now_epoch: float | None = None, allow_expired: bool = False) -> str | None:
    if cookies_file is None:
        return None
    if not cookies_file.exists():
        raise FileNotFoundError(cookies_file)
    current_epoch = time.time() if now_epoch is None else now_epoch
    lines = cookies_file.read_text(encoding="utf-8").splitlines()
    direct_cookie_lines: list[str] = []
    cookie_pairs: list[str] = []
    expired_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("cookie:"):
            direct_cookie_lines.append(stripped.split(":", 1)[1].strip())
            continue
        if "\t" not in stripped and "=" in stripped and not stripped.startswith("#"):
            direct_cookie_lines.append(stripped)
            continue
        if stripped.startswith("#HttpOnly_"):
            stripped = stripped.removeprefix("#HttpOnly_")
        elif stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) < 7:
            continue
        try:
            expires_at = int(parts[4])
        except ValueError:
            expires_at = 0
        if expires_at > 0 and expires_at <= current_epoch and not allow_expired:
            expired_count += 1
            continue
        name = parts[5].strip()
        value = _strip_cookie_value_quotes(parts[6].strip())
        if name:
            cookie_pairs.append(f"{name}={value}")
    if direct_cookie_lines:
        return "; ".join(part.strip().rstrip(";") for part in direct_cookie_lines if part.strip())
    if cookie_pairs:
        return "; ".join(cookie_pairs)
    if expired_count:
        raise ValueError(f"Only expired cookies found in {cookies_file}; please refresh admin cookies")
    raise ValueError(f"No cookies found in {cookies_file}")


def post_json(url: str, payload: dict[str, Any], *, timeout: float, cookie_header: str | None = None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    request = Request(
        url,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            return {
                "status": response.status,
                "body": json.loads(response_body) if response_body else None,
            }
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


def _flatten_groups(groups: list[list[str]] | None) -> list[str]:
    return [item for group in (groups or []) for item in group]


def cookie_names(cookie_header: str | None) -> list[str]:
    if not cookie_header:
        return []
    return [part.split("=", 1)[0].strip() for part in cookie_header.split(";") if "=" in part]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload curated interaction plans to the backend interaction-assets API.")
    parser.add_argument("--curated-root", type=Path, default=DEFAULT_CURATED_ROOT)
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--video-id", nargs="+", action="append", help="Only upload exact video ids, such as beiwang_ep01.")
    parser.add_argument("--interaction-mode", nargs="+", action="append", help="Only upload selected interaction modes.")
    parser.add_argument("--canonical-series-id", help="Override canonical_series_id for all uploaded assets.")
    parser.add_argument("--cookies-file", type=Path, default=DEFAULT_COOKIES_FILE, help="Cookies file used for backend login.")
    parser.add_argument("--append", action="store_true", help="Set replace_existing=false.")
    parser.add_argument("--execute", action="store_true", help="Actually POST to backend. Omit for dry-run.")
    parser.add_argument("--timeout-sec", type=float, default=30.0)
    parser.add_argument("--print-payload", action="store_true", help="Print full request payloads.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    video_ids = discover_video_ids(args.curated_root, video_ids=_flatten_groups(args.video_id))
    interaction_mode_filter = set(_flatten_groups(args.interaction_mode))
    replace_existing = not args.append
    uploaded = 0
    failed: list[tuple[str, str, str]] = []
    cookie_header: str | None = None
    if args.execute:
        try:
            cookie_header = load_cookie_header(args.cookies_file)
        except Exception as exc:  # noqa: BLE001 - report auth setup errors as upload failures.
            print(f"FAIL cookies: {exc}")
            return 1

    mode_label = "EXECUTE" if args.execute else "DRY-RUN"
    print(
        f"{mode_label} backend={args.backend_url} curated_root={args.curated_root} "
        f"videos={len(video_ids)} cookies_file={args.cookies_file}"
    )
    if args.execute:
        names = cookie_names(cookie_header)
        print(f"COOKIES loaded={len(names)} names={','.join(names)}")
    for video_id in video_ids:
        try:
            plan = load_curated_plan(args.curated_root, video_id)
            payloads = build_upload_payloads_for_video(
                video_id=video_id,
                plan=plan,
                replace_existing=replace_existing,
                canonical_series_id=args.canonical_series_id,
            )
        except Exception as exc:  # noqa: BLE001 - batch upload should report per-video failures.
            failed.append((video_id, "*", str(exc)))
            print(f"FAIL {video_id}: {exc}")
            continue

        if interaction_mode_filter:
            payloads = [payload for payload in payloads if payload["interaction_mode"] in interaction_mode_filter]
        if not payloads:
            print(f"SKIP {video_id}: no matching interaction assets")
            continue

        for payload in payloads:
            interaction_mode = str(payload["interaction_mode"])
            url = build_upload_url(args.backend_url, video_id)
            print(
                f"{'POST' if args.execute else 'WOULD POST'} {video_id} "
                f"mode={interaction_mode} items={len(payload['items'])} "
                f"replace_existing={payload['replace_existing']} url={url}"
            )
            if args.print_payload:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            if not args.execute:
                continue
            try:
                response = post_json(url, payload, timeout=args.timeout_sec, cookie_header=cookie_header)
            except Exception as exc:  # noqa: BLE001 - batch upload should continue and report all failures.
                failed.append((video_id, interaction_mode, str(exc)))
                print(f"FAIL {video_id} mode={interaction_mode}: {exc}")
                continue
            uploaded += 1
            print(f"OK {video_id} mode={interaction_mode}: status={response['status']}")

    print(f"DONE uploaded={uploaded} failed={len(failed)} dry_run={not args.execute}")
    if failed:
        for video_id, interaction_mode, error in failed:
            print(f"FAILED {video_id} mode={interaction_mode}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

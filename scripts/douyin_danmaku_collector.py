#!/usr/bin/env python3
"""Discover and fetch Douyin danmaku for the short-drama dataset.

The browser is used to capture a valid get_v2 request. Once captured, the main
path fetches rewritten time windows inside the Douyin page context, matching the
manual Console workflow that has already worked for this dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from threading import Event
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_MANIFEST = Path("configs/douyin_episodes.json")
DEFAULT_OUT_DIR = Path("data/raw/episodes")
DEFAULT_FAILED_PATH = Path("data/raw/danmaku_failed.json")
DEFAULT_SEEDS_PATH = Path("data/raw/danmaku_seed_urls.json")
DEFAULT_USER_DATA_DIR = Path(".playwright/douyin-profile")
DEFAULT_STEP_MS = 32_000
DEFAULT_INTERVAL_MS = 2_000
DEFAULT_EPISODE_DELAY_SEC = 20

SERIES_SLUGS = {
    "云渺1：我修仙多年强亿点怎么了": "yunmiao_1",
    "北往": "beiwang",
    "北派寻宝笔记": "beipai_xunbao_biji",
    "十八岁太奶奶驾到，重整家族荣耀第三部": "shibasui_tainainai",
    "天下第一纨绔": "tianxia_diyi_wanku",
    "家里家外": "jiali_jiawai",
    "幸得相遇离婚时": "xingde_xiangyu_lihunshi",
    "撕夜": "siye",
    "荒年全村啃树皮，我有系统满仓肉": "huangnian_quancun_kenshupi",
    "那年冬至": "nanian_dongzhi",
}


def log(message: str) -> None:
    print(message, flush=True)


def normalize_episode_id(value: Any) -> str:
    raw = str(value).strip()
    if raw.startswith("douyin_"):
        raw = raw.removeprefix("douyin_")
    if not raw.isdigit():
        raise ValueError(f"episode_id must be a Douyin numeric video id, got: {value}")
    return raw


def normalize_episode_no(value: Any) -> tuple[str, str]:
    raw = str(value).strip()
    match = re.search(r"\d+", raw)
    if not match:
        raise ValueError(f"episode_no must contain digits, got: {value}")
    number = int(match.group(0))
    if number <= 0:
        raise ValueError(f"episode_no must be positive, got: {value}")
    return str(number), f"ep{number:02d}"


def _episode_from_csv_row(row: dict[str, str], index: int) -> dict[str, str]:
    series_name = (row.get("series_name") or "").strip()
    episode_no_raw = (row.get("episode_no") or "").strip()
    douyin_video_id = (row.get("douyin_video_id") or row.get("episode_id") or "").strip()

    if not series_name:
        raise ValueError(f"CSV row {index} is missing series_name")
    if series_name not in SERIES_SLUGS:
        raise ValueError(f"CSV row {index} has unknown series_name: {series_name}")
    if not episode_no_raw:
        raise ValueError(f"CSV row {index} is missing episode_no")
    if not douyin_video_id:
        raise ValueError(f"CSV row {index} is missing douyin_video_id")

    episode_no, episode_label = normalize_episode_no(episode_no_raw)
    video_id = normalize_episode_id(douyin_video_id)
    return {
        "episode_id": video_id,
        "video_id": video_id,
        "video_url": f"https://www.douyin.com/video/{video_id}",
        "series_name": series_name,
        "series_id": SERIES_SLUGS[series_name],
        "episode_no": episode_no,
        "episode_label": episode_label,
    }


def _csv_has_header(first_row: list[str]) -> bool:
    normalized = {cell.strip() for cell in first_row}
    return {"series_name", "episode_no", "douyin_video_id"}.issubset(normalized)


def load_csv_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("CSV manifest is empty")

    if _csv_has_header(rows[0]):
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            return [
                _episode_from_csv_row(
                    {str(key): str(value) for key, value in row.items() if key is not None},
                    index,
                )
                for index, row in enumerate(reader, start=2)
                if any((value or "").strip() for value in row.values())
            ]

    episodes: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        if len(row) < 3:
            raise ValueError(f"CSV row {index} must have at least 3 columns")
        episodes.append(
            _episode_from_csv_row(
                {
                    "series_name": row[0],
                    "episode_no": row[1],
                    "douyin_video_id": row[2],
                },
                index,
            )
        )
    return episodes


def load_manifest(path: Path) -> list[dict[str, str]]:
    """Load minimal episode manifest: [{"episode_id": "763..."}]."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("manifest must be a JSON array")

    episodes: list[dict[str, str]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"manifest item {index} must be an object")
        if "episode_id" not in item:
            raise ValueError(f"manifest item {index} is missing episode_id")
        video_id = normalize_episode_id(item["episode_id"])
        episodes.append(
            {
                "episode_id": video_id,
                "video_id": video_id,
                "video_url": f"https://www.douyin.com/video/{video_id}",
            }
        )
    return episodes


def format_episode_label(episode: dict[str, str]) -> str:
    return " ".join(
        part
        for part in [
            episode.get("episode_id", ""),
            episode.get("series", ""),
            episode.get("episode", ""),
            episode.get("title", ""),
        ]
        if part
    )


def episode_file_stem(episode: dict[str, str]) -> str:
    return f"douyin_{episode['video_id']}"


def episode_output_path(out_dir: Path, episode: dict[str, str], dataset_layout: bool) -> Path:
    if not dataset_layout:
        return out_dir / f"{episode_file_stem(episode)}.json"

    try:
        series_id = episode["series_id"]
        episode_label = episode["episode_label"]
    except KeyError as exc:
        raise ValueError(
            "dataset output layout requires CSV episode fields: series_id and episode_label"
        ) from exc
    return out_dir / "raw" / series_id / episode_label / "douyin.json"


def _replace_query_params(url: str, replacements: dict[str, str]) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(replacements)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _query_int(url: str, name: str) -> int:
    parts = urlsplit(url)
    values = dict(parse_qsl(parts.query, keep_blank_values=True))
    raw = values.get(name)
    if raw is None:
        raise ValueError(f"missing required query parameter: {name}")
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid integer query parameter {name}: {raw}") from exc


def _query_value(url: str, name: str) -> str | None:
    parts = urlsplit(url)
    values = dict(parse_qsl(parts.query, keep_blank_values=True))
    return values.get(name)


def make_window_key(url: str) -> str:
    start = _query_value(url, "start_time") or "unknown"
    end = _query_value(url, "end_time") or "unknown"
    return f"{start}-{end}"


def build_window_urls(seed_url: str, step_ms: int = DEFAULT_STEP_MS) -> list[str]:
    """Create get_v2 URLs covering the full video duration."""
    duration = _query_int(seed_url, "duration")
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")
    if step_ms <= 0:
        raise ValueError(f"step_ms must be positive, got {step_ms}")

    urls = []
    for start in range(0, duration, step_ms):
        end = min(start + step_ms, duration)
        urls.append(
            _replace_query_params(
                seed_url,
                {
                    "start_time": str(start),
                    "end_time": str(end),
                },
            )
        )
    return urls


def expected_seek_points(duration_ms: int, step_ms: int) -> list[float]:
    points: list[float] = []
    for start_ms in range(0, duration_ms, step_ms):
        points.append(max(0, start_ms / 1000 + 0.2))
    return points


def deduplicate_and_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by danmaku_id and sort by offset_time."""
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        danmaku_id = item.get("danmaku_id")
        if danmaku_id is None:
            danmaku_id = f"missing:{len(deduped)}:{item.get('offset_time')}:{item.get('text')}"
        key = str(danmaku_id)
        if key not in deduped:
            deduped[key] = item
    return sorted(deduped.values(), key=lambda x: x.get("offset_time") or 0)


def normalize_danmaku(item: dict[str, Any]) -> dict[str, Any]:
    """Keep only analysis-ready fields while preserving raw payload."""
    time_ms = item.get("offset_time") or 0
    return {
        "danmaku_id": item.get("danmaku_id"),
        "item_id": item.get("item_id"),
        "user_id": item.get("user_id"),
        "time_ms": time_ms,
        "time_sec": time_ms / 1000,
        "text": item.get("text"),
        "digg_count": item.get("digg_count"),
        "score": item.get("score"),
        "has_emoji": item.get("has_emoji"),
        "danmaku_type": item.get("danmaku_type"),
        "is_ad": item.get("is_ad"),
        "raw": item,
    }


def summarize_danmaku_response(
    data: dict[str, Any],
    status: int,
    start_time: str | None,
    end_time: str | None,
) -> dict[str, Any]:
    items = data.get("danmaku_list") or []
    status_msg = data.get("status_msg")
    return {
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "json_keys": sorted(data.keys()),
        "status_code": data.get("status_code"),
        "status_msg": status_msg,
        "blocked": status_msg == "blocked",
        "total": data.get("total"),
        "danmaku_list_count": len(items),
    }


def needs_seek_fallback(raw_items: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> bool:
    if raw_items:
        return False
    return bool(diagnostics) and all(row.get("blocked") for row in diagnostics)


def extract_metadata(aweme_detail: dict[str, Any]) -> dict[str, Any]:
    statistics = aweme_detail.get("statistics") or {}
    author = aweme_detail.get("author") or {}
    mix_info = aweme_detail.get("mix_info") or {}
    mix_statis = mix_info.get("statis") or {}
    return {
        "title": aweme_detail.get("desc"),
        "duration_ms": aweme_detail.get("duration"),
        "series": {
            "id": mix_info.get("mix_id"),
            "name": mix_info.get("mix_name"),
            "description": mix_info.get("desc"),
            "total_episode": mix_statis.get("total_episode"),
            "current_episode": mix_statis.get("current_episode"),
            "updated_to_episode": mix_statis.get("updated_to_episode"),
        },
        "stats": {
            "digg_count": statistics.get("digg_count"),
            "comment_count": statistics.get("comment_count"),
            "collect_count": statistics.get("collect_count"),
            "share_count": statistics.get("share_count"),
            "play_count": statistics.get("play_count"),
            "series_play_vv": mix_statis.get("play_vv"),
            "series_collect_vv": mix_statis.get("collect_vv"),
        },
        "author": {
            "uid": author.get("uid"),
            "sec_uid": author.get("sec_uid"),
            "nickname": author.get("nickname"),
        },
        "raw": aweme_detail,
    }


def make_episode_payload(
    episode: dict[str, str],
    metadata: dict[str, Any] | None,
    seed_url: str,
    raw_items: list[dict[str, Any]],
    collect_mode: str,
    observed_response: dict[str, Any] | None,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    deduped = deduplicate_and_sort(raw_items)
    clean = [normalize_danmaku(item) for item in deduped]
    return {
        "source": "douyin",
        "episode_id": episode["episode_id"],
        "video_id": episode["video_id"],
        "video_url": episode["video_url"],
        "group_id": _query_value(seed_url, "group_id"),
        "item_id": _query_value(seed_url, "item_id"),
        "metadata": metadata,
        "danmaku": {
            "raw_count": len(raw_items),
            "count": len(clean),
            "items": clean,
        },
        "diagnostics": {
            "collect_mode": collect_mode,
            "observed_seed_response": observed_response,
            "fetch_windows": diagnostics,
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def merge_seed_urls(path: Path, new_seeds: dict[str, str]) -> dict[str, str]:
    existing: dict[str, str] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = {str(key): str(value) for key, value in loaded.items()}
        except json.JSONDecodeError:
            existing = {}
    return {**existing, **new_seeds}


def discover_seed_url(page: Any, video_url: str, timeout_ms: int) -> tuple[str, dict[str, Any] | None]:
    """Open a video page and return the first get_v2 request URL and response summary."""
    found = Event()
    captured: dict[str, str] = {}
    response_summary: dict[str, Any] | None = None

    def on_request(request: Any) -> None:
        url = request.url
        if "get_v2" in url and "duration=" in url:
            captured.setdefault("url", url)
            found.set()

    def on_response(response: Any) -> None:
        nonlocal response_summary
        url = response.url
        if response_summary is not None:
            return
        if "get_v2" not in url or "duration=" not in url:
            return
        try:
            data = response.json()
        except Exception as exc:
            response_summary = {
                "status": response.status,
                "response_error": f"{type(exc).__name__}: {exc}",
            }
            return
        response_summary = summarize_danmaku_response(
            data,
            response.status,
            _query_value(url, "start_time"),
            _query_value(url, "end_time"),
        )

    page.on("request", on_request)
    page.on("response", on_response)
    page.goto(video_url, wait_until="domcontentloaded", timeout=timeout_ms)

    try:
        page.locator("video").first.click(timeout=3_000)
    except Exception:
        pass

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if found.wait(timeout=0.5):
            response_deadline = time.monotonic() + 5
            while response_summary is None and time.monotonic() < response_deadline:
                page.wait_for_timeout(100)
            return captured["url"], response_summary
        try:
            page.mouse.wheel(0, 300)
        except Exception:
            pass

    raise TimeoutError(f"did not observe get_v2 request within {timeout_ms} ms")


def fetch_metadata_in_page(page: Any, video_id: str) -> dict[str, Any] | None:
    """Fetch aweme detail metadata from inside the current Douyin page context."""
    log(f"[metadata] fetching aweme detail for {video_id}")
    result = page.evaluate(
        """async videoId => {
            const endpoint = `/aweme/v1/web/aweme/detail/?aweme_id=${videoId}&aid=6383&version_name=17.4.0&device_platform=webapp`;
            const response = await fetch(endpoint, {
                method: "GET",
                credentials: "include",
                headers: {
                    accept: "application/json, text/plain, */*"
                }
            });
            const data = await response.json();
            return {
                status: response.status,
                status_code: data.status_code,
                keys: Object.keys(data).sort(),
                aweme_detail: data.aweme_detail || null
            };
        }""",
        video_id,
    )
    if not result.get("aweme_detail"):
        log(
            "[metadata] missing aweme_detail "
            f"status={result.get('status')} status_code={result.get('status_code')} "
            f"keys={','.join(result.get('keys') or [])}"
        )
        return None
    metadata = extract_metadata(result["aweme_detail"])
    log(
        "[metadata-done] "
        f"title={metadata.get('title')} "
        f"series={(metadata.get('series') or {}).get('name')} "
        f"duration_ms={metadata.get('duration_ms')}"
    )
    return metadata


def fetch_danmaku_windows_in_page(
    page: Any,
    seed_url: str,
    step_ms: int,
    interval_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch danmaku windows from inside the current Douyin page context."""
    all_items: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    window_urls = build_window_urls(seed_url, step_ms=step_ms)
    for index, window_url in enumerate(window_urls, start=1):
        start_time = _query_value(window_url, "start_time")
        end_time = _query_value(window_url, "end_time")
        log(f"[fetch] window {index}/{len(window_urls)} {start_time}-{end_time}")
        result = page.evaluate(
            """async url => {
                const response = await fetch(url, {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        accept: "application/json, text/plain, */*",
                        "x-secsdk-csrf-token": "DOWNGRADE"
                    }
                });
                const data = await response.json();
                return {
                    status: response.status,
                    data
                };
            }""",
            window_url,
        )
        data = result["data"]
        items = data.get("danmaku_list") or []
        all_items.extend(items)
        summary = summarize_danmaku_response(
            data,
            result["status"],
            start_time,
            end_time,
        )
        diagnostics.append(summary)
        log(
            "[fetch-done] "
            f"window {index}/{len(window_urls)} "
            f"status={summary['status']} "
            f"total={summary['total']} "
            f"count={summary['danmaku_list_count']} "
            f"status_msg={summary['status_msg']}"
        )
        time.sleep(interval_ms / 1000)

    return all_items, diagnostics


def observe_page_danmaku(
    page: Any,
    seed_url: str,
    duration_ms: int,
    step_ms: int,
    settle_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect danmaku from real page responses while seeking through the video."""
    all_items: list[dict[str, Any]] = []
    diagnostics_by_window: dict[str, dict[str, Any]] = {}

    def on_response(response: Any) -> None:
        url = response.url
        if "get_v2" not in url or "duration=" not in url:
            return
        try:
            data = response.json()
        except Exception as exc:
            diagnostics_by_window[make_window_key(url)] = {
                "start_time": _query_value(url, "start_time"),
                "end_time": _query_value(url, "end_time"),
                "status": response.status,
                "response_error": f"{type(exc).__name__}: {exc}",
            }
            return
        items = data.get("danmaku_list") or []
        all_items.extend(items)
        diagnostics_by_window[make_window_key(url)] = summarize_danmaku_response(
            data,
            response.status,
            _query_value(url, "start_time"),
            _query_value(url, "end_time"),
        )

    page.on("response", on_response)

    for second in expected_seek_points(duration_ms, step_ms):
        try:
            page.evaluate(
                """second => {
                    const video = document.querySelector('video');
                    if (!video) return false;
                    video.currentTime = Math.min(second, Math.max(0, video.duration || second));
                    video.play().catch(() => {});
                    return true;
                }""",
                second,
            )
        except Exception:
            pass
        page.wait_for_timeout(settle_ms)

    seed_key = make_window_key(seed_url)
    if seed_key not in diagnostics_by_window:
        diagnostics_by_window[seed_key] = {
            "start_time": _query_value(seed_url, "start_time"),
            "end_time": _query_value(seed_url, "end_time"),
            "status": None,
            "note": "seed response was observed before page collection listener attached",
        }

    diagnostics = sorted(
        diagnostics_by_window.values(),
        key=lambda row: int(row.get("start_time") or 0)
        if str(row.get("start_time") or "").isdigit()
        else 0,
    )
    return all_items, diagnostics


def fetch_danmaku_windows(
    context: Any,
    seed_url: str,
    step_ms: int,
    interval_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch all danmaku windows through Playwright's cookie-aware request API."""
    all_items: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for window_url in build_window_urls(seed_url, step_ms=step_ms):
        start_time = _query_value(window_url, "start_time")
        end_time = _query_value(window_url, "end_time")
        response = context.request.get(
            window_url,
            headers={
                "accept": "application/json, text/plain, */*",
                "x-secsdk-csrf-token": "DOWNGRADE",
            },
            timeout=30_000,
        )
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status}: {response.status_text}")
        data = response.json()
        items = data.get("danmaku_list") or []
        all_items.extend(items)
        diagnostics.append(summarize_danmaku_response(data, response.status, start_time, end_time))
        time.sleep(interval_ms / 1000)
    return all_items, diagnostics


def run_collection(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    dataset_layout = args.csv is not None
    episodes = load_csv_manifest(args.csv) if dataset_layout else load_manifest(args.manifest)
    selected = episodes[: args.limit] if args.limit else episodes
    root_out_dir = args.output_dir if dataset_layout else args.out_dir
    root_out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[dict[str, str]] = []
    seeds: dict[str, str] = {}

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(args.user_data_dir),
            headless=not args.headed,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        try:
            if args.login:
                page = context.new_page()
                try:
                    log(
                        "[login] opening Douyin. Log in in the browser window; "
                        f"waiting {args.login_wait_sec} seconds."
                    )
                    page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60_000)
                    time.sleep(args.login_wait_sec)
                    log("[login] continuing with saved browser profile")
                finally:
                    page.close()

            for index, episode in enumerate(selected, start=1):
                file_stem = episode_file_stem(episode)
                out_path = episode_output_path(root_out_dir, episode, dataset_layout=dataset_layout)
                if out_path.exists() and not args.force:
                    log(f"[skip] {index}/{len(selected)} {file_stem} already exists")
                    continue

                label = format_episode_label(episode)
                log(f"[open] {index}/{len(selected)} {label}")
                log(f"[url] {episode['video_url']}")
                page = context.new_page()
                try:
                    seed_url, observed_response = discover_seed_url(
                        page,
                        episode["video_url"],
                        args.timeout_ms,
                    )
                    seeds[file_stem] = seed_url
                    log(f"[seed] {file_stem} get_v2 captured")
                    if observed_response:
                        log(
                            "[observed] "
                            f"status={observed_response.get('status')} "
                            f"status_msg={observed_response.get('status_msg')} "
                            f"count={observed_response.get('danmaku_list_count')} "
                            f"keys={','.join(observed_response.get('json_keys', []))}"
                        )

                    metadata = fetch_metadata_in_page(page, episode["video_id"])
                    raw_items, diagnostics = fetch_danmaku_windows_in_page(
                        page,
                        seed_url,
                        step_ms=args.step_ms,
                        interval_ms=args.interval_ms,
                    )
                    collect_mode = "page_fetch"
                    if needs_seek_fallback(raw_items, diagnostics):
                        log("[fallback] page fetch was blocked; trying seek observation")
                        raw_items, diagnostics = observe_page_danmaku(
                            page,
                            seed_url,
                            duration_ms=_query_int(seed_url, "duration"),
                            step_ms=args.step_ms,
                            settle_ms=args.settle_ms,
                        )
                        collect_mode = "seek_observe"
                    payload = make_episode_payload(
                        episode=episode,
                        metadata=metadata,
                        seed_url=seed_url,
                        raw_items=raw_items,
                        collect_mode=collect_mode,
                        observed_response=observed_response,
                        diagnostics=diagnostics,
                    )
                    write_json(out_path, payload)
                    for row in diagnostics:
                        log(
                            "[window] "
                            f"{row['start_time']}-{row['end_time']} "
                            f"status={row['status']} "
                            f"total={row['total']} "
                            f"count={row['danmaku_list_count']} "
                            f"keys={','.join(row['json_keys'])}"
                        )
                    log(
                        f"[saved] {out_path} "
                        f"raw={payload['danmaku']['raw_count']} "
                        f"dedup={payload['danmaku']['count']}"
                    )
                except Exception as exc:
                    failures.append(
                        {
                            **episode,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    log(f"[failed] {file_stem} {type(exc).__name__}: {exc}")
                finally:
                    page.close()
                    if index < len(selected) and args.episode_delay_sec > 0:
                        log(f"[cooldown] waiting {args.episode_delay_sec}s before next episode")
                        time.sleep(args.episode_delay_sec)
        finally:
            context.close()

    if seeds:
        write_json(args.seeds_path, merge_seed_urls(args.seeds_path, seeds))
    if failures:
        write_json(args.failed_path, failures)
        log(f"[done] failures={len(failures)} written to {args.failed_path}")
        return 1

    log("[done] all episodes collected")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover Douyin get_v2 danmaku requests and fetch all windows.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "CSV targets with columns series_name, episode_no, douyin_video_id. "
            "When set, outputs use <output-dir>/raw/<series_id>/epXX/douyin.json."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/qinminghao/Desktop/ByteDance/VideoData"),
        help="External VideoData root used by --csv mode.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--failed-path", type=Path, default=DEFAULT_FAILED_PATH)
    parser.add_argument("--seeds-path", type=Path, default=DEFAULT_SEEDS_PATH)
    parser.add_argument("--user-data-dir", type=Path, default=DEFAULT_USER_DATA_DIR)
    parser.add_argument("--step-ms", type=int, default=DEFAULT_STEP_MS)
    parser.add_argument("--interval-ms", type=int, default=DEFAULT_INTERVAL_MS)
    parser.add_argument(
        "--episode-delay-sec",
        type=int,
        default=DEFAULT_EPISODE_DELAY_SEC,
        help="Seconds to wait after each episode before opening the next one.",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=1_800,
        help="Milliseconds to wait after each in-page seek while observing real get_v2 responses.",
    )
    parser.add_argument("--timeout-ms", type=int, default=45_000)
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N videos.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--headed", action="store_true", help="Show Chromium window.")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open Douyin first and wait for manual login before collecting.",
    )
    parser.add_argument(
        "--login-wait-sec",
        type=int,
        default=90,
        help="Seconds to wait for manual login when --login is set.",
    )
    return parser


def main() -> int:
    return run_collection(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

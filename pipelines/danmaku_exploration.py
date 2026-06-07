from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from scripts.algorithm_danmaku_csv import DANMAKU_CSV_ENCODINGS, SERIES_SLUGS, normalize_episode_id


REQUIRED_COLUMNS = (
    "剧名称",
    "group_title",
    "发弹幕时刻相对于视频起始时间偏移量",
    "累计点赞数",
    "弹幕内容",
)

LOW_SIGNAL_TEXTS = {
    "哈哈",
    "哈哈哈",
    "哈哈哈哈",
    "哈哈哈哈哈",
    "啊啊啊",
    "啊啊啊啊",
}

UNSAFE_KEYWORDS = ("傻逼", "sb", "滚", "去死", "垃圾")
ACTOR_CHARM_KEYWORDS = ("帅", "美", "漂亮", "好看", "眼神", "表情", "演技", "哭戏", "气质", "老公", "老婆", "姐姐", "小奶狗")
PLOT_REACTION_KEYWORDS = ("终于", "怼", "反转", "打脸", "反杀", "真相", "原来", "醒悟", "报仇", "争气")
MEME_KEYWORDS = ("顶得住", "顶不住", "禁止", "会演", "笑不活", "蚌埠住", "绷不住", "名场面")
EMOTION_BURST_KEYWORDS = ("哈哈", "笑死", "笑不活", "爽", "啊啊", "哭了", "甜")
STANCE_KEYWORDS = ("别原谅", "站", "选", "支持", "不配", "离开他")


@dataclass(frozen=True)
class ExplorationDanmakuItem:
    comment_id: str
    series_title: str
    series_id: str
    episode_title: str
    episode_id: str
    video_id: str
    time_sec: float
    digg_count: int
    text: str
    clean_text: str
    low_quality: bool


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _compact_text(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _is_low_quality_text(text: str) -> bool:
    compact = _compact_text(text)
    if not compact:
        return True
    if compact in LOW_SIGNAL_TEXTS:
        return True
    if re.fullmatch(r"[\W_]+", compact):
        return True
    if re.fullmatch(r"\d+", compact):
        return True
    if re.fullmatch(r"(哈|啊|呀|？|\?)+", compact):
        return True
    return False


def _fallback_series_id(series_title: str) -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "_", series_title.lower()).strip("_")
    if ascii_slug:
        return ascii_slug
    digest = hashlib.sha1(series_title.encode("utf-8")).hexdigest()[:10]
    return f"series_{digest}"


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    last_error: UnicodeDecodeError | None = None
    for encoding in DANMAKU_CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    return [], encoding
                missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
                if missing:
                    raise ValueError(f"missing required columns: {', '.join(missing)}")
                return [dict(row) for row in reader], encoding
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise UnicodeDecodeError(last_error.encoding, last_error.object, last_error.start, last_error.end, "unable to decode danmaku csv")
    return [], DANMAKU_CSV_ENCODINGS[0]


def _normalize_row(row: dict[str, Any], *, row_number: int) -> tuple[ExplorationDanmakuItem | None, str | None]:
    series_title = _clean_text(row.get("剧名称"))
    episode_title = _clean_text(row.get("group_title"))
    episode_id = normalize_episode_id(episode_title)
    text = _clean_text(row.get("弹幕内容"))
    if not series_title or not episode_id or not text:
        return None, "missing_required_value"

    try:
        time_ms = float(row.get("发弹幕时刻相对于视频起始时间偏移量") or 0.0)
    except (TypeError, ValueError):
        return None, "invalid_time"
    if time_ms < 0:
        return None, "invalid_time"

    try:
        digg_count = int(float(row.get("累计点赞数") or 0))
    except (TypeError, ValueError):
        digg_count = 0

    series_id = SERIES_SLUGS.get(series_title, _fallback_series_id(series_title))
    video_id = f"{series_id}_{episode_id}"
    clean_text = _clean_text(text)
    return (
        ExplorationDanmakuItem(
            comment_id=f"csv_{video_id}_{row_number}",
            series_title=series_title,
            series_id=series_id,
            episode_title=episode_title,
            episode_id=episode_id,
            video_id=video_id,
            time_sec=_round_time(time_ms / 1000.0),
            digg_count=max(0, digg_count),
            text=text,
            clean_text=clean_text,
            low_quality=_is_low_quality_text(clean_text),
        ),
        None,
    )


def load_exploration_danmaku_csv(path: Path) -> tuple[list[ExplorationDanmakuItem], dict[str, Any]]:
    rows, encoding = _read_csv_rows(path)
    items: list[ExplorationDanmakuItem] = []
    skipped_reasons: Counter[str] = Counter()
    for index, row in enumerate(rows, start=1):
        item, skipped_reason = _normalize_row(row, row_number=index)
        if item is None:
            skipped_reasons[str(skipped_reason or "unknown")] += 1
            continue
        items.append(item)
    return (
        sorted(items, key=lambda item: (item.video_id, item.time_sec, item.comment_id)),
        {
            "encoding": encoding,
            "raw_row_count": len(rows),
            "normalized_row_count": len(items),
            "skipped_row_count": sum(skipped_reasons.values()),
            "skipped_reasons": dict(skipped_reasons),
        },
    )


def _item_to_comment(item: ExplorationDanmakuItem) -> dict[str, Any]:
    return {
        "comment_id": item.comment_id,
        "time_sec": item.time_sec,
        "digg_count": item.digg_count,
        "text": item.text,
        "clean_text": item.clean_text,
        "low_quality": item.low_quality,
        "intent_type": classify_intent(item.clean_text, low_quality=item.low_quality),
    }


def _top_comments(items: list[ExplorationDanmakuItem], *, limit: int = 8) -> list[dict[str, Any]]:
    sorted_items = sorted(items, key=lambda item: (-item.digg_count, item.time_sec, item.comment_id))
    comments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted_items:
        if item.clean_text in seen:
            continue
        seen.add(item.clean_text)
        comments.append(_item_to_comment(item))
        if len(comments) >= limit:
            break
    return comments


def build_episode_profiles(items_by_video: dict[str, list[ExplorationDanmakuItem]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for video_id, items in sorted(items_by_video.items()):
        clean_items = [item for item in items if not item.low_quality]
        text_counts = Counter(item.clean_text for item in items)
        profiles.append(
            {
                "video_id": video_id,
                "series_title": items[0].series_title,
                "series_id": items[0].series_id,
                "episode_title": items[0].episode_title,
                "episode_id": items[0].episode_id,
                "danmaku_count": len(items),
                "clean_danmaku_count": len(clean_items),
                "time_range_sec": [_round_time(min(item.time_sec for item in items)), _round_time(max(item.time_sec for item in items))],
                "digg_distribution": {
                    "zero": sum(1 for item in items if item.digg_count == 0),
                    "positive": sum(1 for item in items if item.digg_count > 0),
                    "gte_5": sum(1 for item in items if item.digg_count >= 5),
                    "max": max(item.digg_count for item in items),
                },
                "low_quality_text_count": sum(1 for item in items if item.low_quality),
                "top_repeated_texts": [
                    {"text": text, "count": count}
                    for text, count in sorted(text_counts.items(), key=lambda value: (-value[1], value[0]))[:10]
                ],
                "top_liked_texts": _top_comments(items, limit=10),
            }
        )
    return profiles


def _build_windows_for_episode(
    *,
    video_id: str,
    items: list[ExplorationDanmakuItem],
    window_sec: float,
    step_sec: float,
    min_window_danmaku_count: int,
    max_windows_per_episode: int,
) -> list[dict[str, Any]]:
    if not items or window_sec <= 0 or step_sec <= 0:
        return []
    raw_windows: list[dict[str, Any]] = []
    start_time = min(item.time_sec for item in items)
    last_time = max(item.time_sec for item in items)
    while start_time <= last_time:
        end_time = start_time + window_sec
        window_items = [item for item in items if start_time <= item.time_sec < end_time]
        if len(window_items) >= min_window_danmaku_count:
            text_counts = Counter(item.clean_text for item in window_items)
            repeat_text_count = max(text_counts.values(), default=0)
            unique_text_count = len(text_counts)
            digg_sum = sum(item.digg_count for item in window_items)
            high_digg_count = sum(1 for item in window_items if item.digg_count >= 5)
            burst_score = max(0.0, len(window_items) - min_window_danmaku_count) * 0.75
            resonance_score = (
                len(window_items)
                + unique_text_count * 0.3
                + max(0, repeat_text_count - 1) * 1.1
                + min(digg_sum, 50) * 0.12
                + high_digg_count * 0.8
                + burst_score
            )
            raw_windows.append(
                {
                    "window_id": f"dw_{video_id}_{len(raw_windows) + 1:03d}",
                    "video_id": video_id,
                    "start_time": _round_time(start_time),
                    "end_time": _round_time(end_time),
                    "danmaku_count": len(window_items),
                    "unique_text_count": unique_text_count,
                    "repeat_text_count": repeat_text_count,
                    "digg_sum": int(digg_sum),
                    "high_digg_count": high_digg_count,
                    "burst_score": _round_time(burst_score),
                    "resonance_score": _round_time(resonance_score),
                    "top_comments": _top_comments(window_items),
                    "_items": window_items,
                }
            )
        start_time = _round_time(start_time + step_sec)

    selected: list[dict[str, Any]] = []
    for window in sorted(raw_windows, key=lambda value: (-float(value["resonance_score"]), float(value["start_time"]))):
        if any(min(float(window["end_time"]), float(existing["end_time"])) > max(float(window["start_time"]), float(existing["start_time"])) for existing in selected):
            continue
        selected.append(window)
        if len(selected) >= max_windows_per_episode:
            break
    return sorted(selected, key=lambda value: float(value["start_time"]))


def classify_intent(text: str, *, low_quality: bool = False) -> str:
    compact = _compact_text(text)
    if any(keyword in compact for keyword in UNSAFE_KEYWORDS):
        return "unsafe"
    if low_quality:
        return "low_signal"
    if any(keyword in compact for keyword in PLOT_REACTION_KEYWORDS):
        return "plot_reaction"
    if any(keyword in compact for keyword in ACTOR_CHARM_KEYWORDS):
        return "actor_charm"
    if any(keyword in compact for keyword in MEME_KEYWORDS):
        return "meme"
    if any(keyword in compact for keyword in STANCE_KEYWORDS):
        return "stance"
    if any(keyword in compact for keyword in EMOTION_BURST_KEYWORDS):
        return "emotion_burst"
    return "low_signal"


def _fit_score_for_text(
    *,
    text: str,
    intent_type: str,
    source_count: int,
    digg_sum: int,
    low_quality: bool,
) -> float:
    compact_len = len(_compact_text(text))
    score = 0.0
    if 6 <= compact_len <= 18:
        score += 0.3
    elif compact_len <= 24:
        score += 0.15
    if intent_type in {"plot_reaction", "actor_charm", "meme"}:
        score += 0.35
    elif intent_type == "stance":
        score += 0.18
    elif intent_type == "emotion_burst":
        score += 0.05
    if source_count >= 2:
        score += 0.15
    if digg_sum >= 3:
        score += 0.12
    if low_quality or intent_type in {"low_signal", "unsafe"}:
        score -= 0.25
    return _round_time(max(0.0, min(score, 1.0)))


def _recommendation_for_score(score: float, intent_type: str) -> str:
    if intent_type == "unsafe":
        return "not_recommended"
    if score >= 0.65:
        return "recommended"
    if score >= 0.35:
        return "borderline"
    return "not_recommended"


def build_review_candidates(windows: list[dict[str, Any]], *, duration_sec: float = 5.0) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for window in windows:
        window_items = list(window.get("_items") or [])
        by_text: dict[str, list[ExplorationDanmakuItem]] = defaultdict(list)
        for item in window_items:
            by_text[item.clean_text].append(item)
        ranked_groups = sorted(
            by_text.values(),
            key=lambda group: (
                -len(group),
                -sum(item.digg_count for item in group),
                min(item.time_sec for item in group),
            ),
        )
        for group in ranked_groups[:5]:
            representative = max(group, key=lambda item: (item.digg_count, -item.time_sec))
            key = (representative.video_id, representative.clean_text)
            if key in seen:
                continue
            seen.add(key)
            intent_type = classify_intent(representative.clean_text, low_quality=representative.low_quality)
            digg_sum = sum(item.digg_count for item in group)
            fit_score = _fit_score_for_text(
                text=representative.clean_text,
                intent_type=intent_type,
                source_count=len(group),
                digg_sum=digg_sum,
                low_quality=representative.low_quality,
            )
            recommendation = _recommendation_for_score(fit_score, intent_type)
            candidates.append(
                {
                    "candidate_id": f"ivrc_{representative.video_id}_{len(candidates) + 1:03d}",
                    "video_id": representative.video_id,
                    "window_id": str(window["window_id"]),
                    "trigger_time": _round_time(min(item.time_sec for item in group)),
                    "duration_sec": _round_time(duration_sec),
                    "text": representative.clean_text,
                    "intent_type": intent_type,
                    "source_comment_ids": [item.comment_id for item in sorted(group, key=lambda item: item.time_sec)],
                    "resonance_score": _round_time(float(window["resonance_score"])),
                    "inner_voice_fit_score": fit_score,
                    "recommendation": recommendation,
                    "reason": _candidate_reason(intent_type=intent_type, source_count=len(group), recommendation=recommendation),
                    "review_status": "unreviewed",
                }
            )
    return sorted(candidates, key=lambda value: (str(value["video_id"]), float(value["trigger_time"]), str(value["candidate_id"])))


def _candidate_reason(*, intent_type: str, source_count: int, recommendation: str) -> str:
    if recommendation == "recommended":
        return f"{intent_type} 表达清晰，且有 {source_count} 条来源弹幕支撑。"
    if recommendation == "borderline":
        return f"{intent_type} 有一定表达价值，但需要人工确认是否适合一推发送。"
    return f"{intent_type} 不适合作为心里话胶囊主候选。"


def _strip_debug_items(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped: list[dict[str, Any]] = []
    for window in windows:
        payload = dict(window)
        payload.pop("_items", None)
        stripped.append(payload)
    return stripped


def explore_danmaku_csv(
    csv_path: Path,
    *,
    window_sec: float = 8.0,
    step_sec: float = 2.0,
    min_window_danmaku_count: int = 4,
    max_windows_per_episode: int = 50,
    duration_sec: float = 5.0,
) -> dict[str, Any]:
    items, diagnostics = load_exploration_danmaku_csv(csv_path)
    items_by_video: dict[str, list[ExplorationDanmakuItem]] = defaultdict(list)
    for item in items:
        items_by_video[item.video_id].append(item)

    windows_with_items: list[dict[str, Any]] = []
    for video_id, video_items in sorted(items_by_video.items()):
        windows_with_items.extend(
            _build_windows_for_episode(
                video_id=video_id,
                items=video_items,
                window_sec=window_sec,
                step_sec=step_sec,
                min_window_danmaku_count=min_window_danmaku_count,
                max_windows_per_episode=max_windows_per_episode,
            )
        )

    candidates = build_review_candidates(windows_with_items, duration_sec=duration_sec)
    return {
        "source_csv": str(csv_path),
        "created_at": now_iso(),
        "parameters": {
            "window_sec": window_sec,
            "step_sec": step_sec,
            "min_window_danmaku_count": min_window_danmaku_count,
            "max_windows_per_episode": max_windows_per_episode,
            "duration_sec": duration_sec,
        },
        "diagnostics": diagnostics,
        "episode_profiles": build_episode_profiles(items_by_video),
        "resonance_windows": _strip_debug_items(windows_with_items),
        "inner_voice_review_candidates": candidates,
    }


def write_danmaku_exploration_output(*, output_root: Path, payload: dict[str, Any]) -> dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    created_at = payload.get("created_at")
    source_csv = payload.get("source_csv")
    diagnostics = payload.get("diagnostics", {})
    profile_payload = {
        "created_at": created_at,
        "source_csv": source_csv,
        "diagnostics": diagnostics,
        "episodes": payload.get("episode_profiles", []),
    }
    windows_payload = {
        "created_at": created_at,
        "source_csv": source_csv,
        "parameters": payload.get("parameters", {}),
        "windows": payload.get("resonance_windows", []),
    }
    candidates_payload = {
        "created_at": created_at,
        "source_csv": source_csv,
        "parameters": payload.get("parameters", {}),
        "candidates": payload.get("inner_voice_review_candidates", []),
    }
    paths = {
        "episode_profile": output_root / "episode_profile.json",
        "resonance_windows": output_root / "resonance_windows.json",
        "inner_voice_review_candidates": output_root / "inner_voice_review_candidates.json",
    }
    paths["episode_profile"].write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["resonance_windows"].write_text(json.dumps(windows_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["inner_voice_review_candidates"].write_text(
        json.dumps(candidates_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return paths


__all__ = [
    "ExplorationDanmakuItem",
    "build_episode_profiles",
    "build_review_candidates",
    "classify_intent",
    "explore_danmaku_csv",
    "load_exploration_danmaku_csv",
    "write_danmaku_exploration_output",
]

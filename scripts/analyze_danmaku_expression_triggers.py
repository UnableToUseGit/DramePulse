from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.algorithm_danmaku_csv import (
    DANMAKU_CSV_ENCODINGS,
    SERIES_SLUGS,
    normalize_episode_id,
)


DEFAULT_CSV_PATH = Path("data/圈选剧前5集弹幕.csv")
DEFAULT_OUTPUT_ROOT = Path("output/danmaku_expression_analysis")

EXPRESSION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("笑死", ("笑死", "笑不活", "笑发财", "哈哈", "绷不住", "乐死", "乐了", "太搞笑")),
    ("爽到了", ("爽", "解气", "打脸", "活该", "报应", "反杀", "漂亮", "牛逼", "过瘾")),
    ("燃起来了", ("燃", "出人头地", "争气", "逆袭", "崛起", "觉醒", "励志", "搞钱", "改变命运")),
    ("震惊", ("震惊", "卧槽", "我去", "啊？", "啊?", "什么情况", "没想到", "原来", "竟然", "反转")),
    ("磕到了", ("磕", "好甜", "甜死", "在一起", "亲", "抱", "撒糖", "般配", "双向奔赴")),
    ("看哭了", ("泪目", "看哭", "破防", "感动", "心疼", "奶奶", "妈妈", "牺牲", "重逢")),
    ("角色魅力", ("好帅", "太帅", "帅死", "老公", "老婆", "姐姐", "好美", "漂亮", "眼神", "可爱", "小奶狗")),
    ("吐槽", ("离谱", "抓马", "尬", "无语", "逆天", "神经", "有病", "服了", "蚌埠住")),
)


@dataclass(frozen=True)
class DanmakuItem:
    series_id: str
    episode_id: str
    time_sec: float
    text: str
    digg_count: int


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in DANMAKU_CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except UnicodeDecodeError:
            continue
    return []


def _normalize_row(row: dict[str, Any]) -> DanmakuItem | None:
    series_name = str(row.get("剧名称") or "").strip()
    series_id = SERIES_SLUGS.get(series_name)
    episode_id = normalize_episode_id(row.get("group_title"))
    text = str(row.get("弹幕内容") or "").strip()
    if not series_id or not episode_id or not text:
        return None
    try:
        time_ms = float(row.get("发弹幕时刻相对于视频起始时间偏移量") or 0.0)
    except (TypeError, ValueError):
        return None
    if time_ms < 0:
        return None
    try:
        digg_count = int(float(row.get("累计点赞数") or 0))
    except (TypeError, ValueError):
        digg_count = 0
    return DanmakuItem(
        series_id=series_id,
        episode_id=episode_id,
        time_sec=_round_time(time_ms / 1000.0),
        text=text,
        digg_count=max(0, digg_count),
    )


def load_csv_items(csv_path: Path) -> list[DanmakuItem]:
    items: list[DanmakuItem] = []
    for row in _read_csv_rows(csv_path):
        item = _normalize_row(row)
        if item is not None:
            items.append(item)
    return sorted(items, key=lambda item: (item.series_id, item.episode_id, item.time_sec, item.text))


def classify_text(text: str) -> list[str]:
    compact_text = "".join(str(text or "").split()).lower()
    compact_text = compact_text.replace("[笑哭]", "").replace("笑哭", "")
    labels: list[str] = []
    for label, keywords in EXPRESSION_PATTERNS:
        if any(keyword.lower() in compact_text for keyword in keywords):
            labels.append(label)
    return labels


def item_signal_score(item: dict[str, Any] | DanmakuItem) -> float:
    digg_count = int(_get_item_value(item, "digg_count", 0) or 0)
    return 1.0 + min(float(digg_count), 20.0) * 0.35


def _get_item_value(item: dict[str, Any] | DanmakuItem, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _to_runtime_item(item: dict[str, Any] | DanmakuItem) -> dict[str, Any]:
    return {
        "series_id": str(_get_item_value(item, "series_id", "")),
        "episode_id": str(_get_item_value(item, "episode_id", "")),
        "time_sec": float(_get_item_value(item, "time_sec", 0.0)),
        "text": str(_get_item_value(item, "text", "")),
        "digg_count": int(_get_item_value(item, "digg_count", 0) or 0),
    }


def _cluster_labeled_items(
    classified_items: list[dict[str, Any]],
    *,
    cluster_gap_sec: float,
) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for item in sorted(classified_items, key=lambda value: float(value["time_sec"])):
        if not current or float(item["time_sec"]) - float(current[-1]["time_sec"]) <= cluster_gap_sec:
            current.append(item)
            continue
        clusters.append(current)
        current = [item]
    if current:
        clusters.append(current)
    return clusters


def _expression_candidates(cluster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    score_by_label: Counter[str] = Counter()
    count_by_label: Counter[str] = Counter()
    for item in cluster:
        for label in item["labels"]:
            score_by_label[label] += float(item["score"])
            count_by_label[label] += 1
    candidates: list[dict[str, Any]] = []
    for label, score in score_by_label.most_common(3):
        candidates.append(
            {
                "primary_expression": label,
                "score": _round_time(score),
                "count": int(count_by_label[label]),
            }
        )
    return candidates


def _cluster_classified_items_by_expression(
    classified_items: list[dict[str, Any]],
    *,
    cluster_gap_sec: float,
) -> list[list[dict[str, Any]]]:
    items_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in classified_items:
        primary_label = str(item["labels"][0])
        label_item = dict(item)
        label_item["labels"] = [primary_label]
        items_by_label[primary_label].append(label_item)

    clusters: list[list[dict[str, Any]]] = []
    for label_items in items_by_label.values():
        clusters.extend(_cluster_labeled_items(label_items, cluster_gap_sec=cluster_gap_sec))
    return sorted(clusters, key=lambda cluster: min(float(item["time_sec"]) for item in cluster))


def _top_comments(cluster: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    sorted_items = sorted(
        cluster,
        key=lambda item: (-int(item["digg_count"]), -float(item["score"]), float(item["time_sec"])),
    )
    comments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted_items:
        text = str(item["text"])
        if text in seen:
            continue
        seen.add(text)
        comments.append(
            {
                "time_sec": _round_time(float(item["time_sec"])),
                "digg_count": int(item["digg_count"]),
                "text": text,
                "labels": list(item["labels"]),
            }
        )
        if len(comments) >= limit:
            break
    return comments


def _build_cluster_payload(
    *,
    video_id: str,
    cluster: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    times = [float(item["time_sec"]) for item in cluster]
    cluster_score = sum(float(item["score"]) for item in cluster)
    peak_item = max(cluster, key=lambda item: (float(item["score"]), int(item["digg_count"])))
    peak_time = float(peak_item["time_sec"])
    return {
        "cluster_id": f"dc_{video_id}_{index:03d}",
        "start_time": _round_time(max(0.0, min(times) - 1.0)),
        "end_time": _round_time(max(times) + 2.0),
        "peak_time": _round_time(peak_time),
        "suggested_trigger_time_range": [
            _round_time(max(0.0, peak_time - 5.0)),
            _round_time(peak_time),
        ],
        "suggested_cue_time_range": [
            _round_time(max(0.0, peak_time - 1.0)),
            _round_time(peak_time + 3.0),
        ],
        "expression_candidates": _expression_candidates(cluster),
        "danmaku_count": len(cluster),
        "score": _round_time(cluster_score),
        "like_sum": int(sum(int(item["digg_count"]) for item in cluster)),
        "top_comments": _top_comments(cluster),
    }


def analyze_episode_danmaku(
    *,
    video_id: str,
    series_id: str,
    episode_id: str,
    items: list[dict[str, Any] | DanmakuItem],
    cluster_gap_sec: float = 5.0,
    min_cluster_score: float = 4.0,
) -> dict[str, Any]:
    runtime_items = [_to_runtime_item(item) for item in items]
    classified_items: list[dict[str, Any]] = []
    for item in runtime_items:
        labels = classify_text(item["text"])
        if not labels:
            continue
        item = dict(item)
        item["labels"] = labels
        item["score"] = item_signal_score(item)
        classified_items.append(item)

    clusters: list[dict[str, Any]] = []
    for raw_cluster in _cluster_classified_items_by_expression(classified_items, cluster_gap_sec=cluster_gap_sec):
        cluster_score = sum(float(item["score"]) for item in raw_cluster)
        if cluster_score < min_cluster_score:
            continue
        clusters.append(
            _build_cluster_payload(
                video_id=video_id,
                cluster=raw_cluster,
                index=len(clusters) + 1,
            )
        )

    return {
        "video_id": video_id,
        "series_id": series_id,
        "episode_id": episode_id,
        "created_at": now_iso(),
        "total_danmaku_count": len(runtime_items),
        "classified_danmaku_count": len(classified_items),
        "cluster_gap_sec": cluster_gap_sec,
        "min_cluster_score": min_cluster_score,
        "clusters": clusters,
    }


def group_items_by_episode(items: list[DanmakuItem]) -> dict[tuple[str, str], list[DanmakuItem]]:
    grouped: dict[tuple[str, str], list[DanmakuItem]] = defaultdict(list)
    for item in items:
        grouped[(item.series_id, item.episode_id)].append(item)
    return dict(grouped)


def write_episode_analysis(*, output_root: Path, payload: dict[str, Any]) -> Path:
    output_dir = output_root / str(payload["video_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "danmaku_expression_analysis.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_summary(*, output_root: Path, episode_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    expression_counts: Counter[str] = Counter()
    cluster_count = 0
    for payload in episode_payloads:
        for cluster in payload["clusters"]:
            cluster_count += 1
            candidates = cluster.get("expression_candidates") or []
            if candidates:
                expression_counts[str(candidates[0]["primary_expression"])] += 1
    return {
        "created_at": now_iso(),
        "output_root": str(output_root),
        "episode_count": len(episode_payloads),
        "cluster_count": cluster_count,
        "expression_cluster_counts": dict(expression_counts.most_common()),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze danmaku peaks as weak labels for expression triggers.")
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH, help="Path to 圈选剧前5集弹幕.csv.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Directory for analysis JSON outputs.")
    parser.add_argument("--series-id", help="Only analyze one normalized series id, for example beiwang.")
    parser.add_argument("--episode-id", help="Only analyze one episode id, for example ep01.")
    parser.add_argument("--cluster-gap-sec", type=float, default=5.0, help="Merge classified danmaku within this gap.")
    parser.add_argument("--min-cluster-score", type=float, default=4.0, help="Minimum weighted score for a cluster.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    items = load_csv_items(args.csv_path)
    grouped = group_items_by_episode(items)
    output_root: Path = args.output_root
    episode_payloads: list[dict[str, Any]] = []

    for (series_id, episode_id), episode_items in sorted(grouped.items()):
        if args.series_id and series_id != args.series_id:
            continue
        if args.episode_id and episode_id != args.episode_id:
            continue
        video_id = f"{series_id}_{episode_id}"
        payload = analyze_episode_danmaku(
            video_id=video_id,
            series_id=series_id,
            episode_id=episode_id,
            items=episode_items,
            cluster_gap_sec=args.cluster_gap_sec,
            min_cluster_score=args.min_cluster_score,
        )
        write_episode_analysis(output_root=output_root, payload=payload)
        episode_payloads.append(payload)

    output_root.mkdir(parents=True, exist_ok=True)
    summary = build_summary(output_root=output_root, episode_payloads=episode_payloads)
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote danmaku expression analysis for {len(episode_payloads)} episodes to {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

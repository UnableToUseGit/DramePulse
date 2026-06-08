from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import re
from typing import Any, Callable

import numpy as np

from pipelines.client.embedding import EmbeddingClientProtocol
from pipelines.danmaku_exploration import ExplorationDanmakuItem, classify_intent, load_exploration_danmaku_csv


SOURCE_COMMENT_ID_LIMIT = 10
EXAMPLE_TEXT_LIMIT = 8
PEAK_INTERVAL_LIMIT = 3
ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class ExpressionGroup:
    group_id: str
    video_id: str
    text: str
    embedding_text: str
    items: tuple[ExplorationDanmakuItem, ...]

    @property
    def comment_count(self) -> int:
        return len(self.items)

    @property
    def digg_sum(self) -> int:
        return sum(item.digg_count for item in self.items)

    @property
    def first_time_sec(self) -> float:
        return min(item.time_sec for item in self.items)


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _compact_text(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def _canonical_text(value: str) -> str:
    compact = _compact_text(value)
    compact = re.sub(r"[!！~～。,.，、…]+$", "", compact)
    compact = re.sub(r"(哈)\1{2,}", r"\1\1", compact)
    compact = re.sub(r"(啊)\1{2,}", r"\1\1", compact)
    return compact


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _connected_components(vectors: list[list[float]], *, threshold: float) -> list[list[int]]:
    if not vectors:
        return []
    parent = list(range(len(vectors)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    normalized = matrix / norms
    block_size = 512
    for start in range(0, len(vectors), block_size):
        end = min(start + block_size, len(vectors))
        similarities = normalized[start:end] @ normalized.T
        for row_offset, row in enumerate(similarities):
            left_index = start + row_offset
            right_indices = np.flatnonzero(row >= threshold)
            for right_index in right_indices:
                if right_index > left_index:
                    union(left_index, int(right_index))

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(vectors)):
        components[find(index)].append(index)
    return list(components.values())


def _build_expression_groups(items: list[ExplorationDanmakuItem]) -> list[ExpressionGroup]:
    by_canonical: dict[str, list[ExplorationDanmakuItem]] = defaultdict(list)
    for item in items:
        if item.low_quality:
            continue
        if classify_intent(item.clean_text, low_quality=item.low_quality) in {"unsafe", "emotion_burst"}:
            continue
        canonical = _canonical_text(item.clean_text)
        if not canonical:
            continue
        by_canonical[canonical].append(item)

    groups: list[ExpressionGroup] = []
    for index, (canonical, group_items) in enumerate(sorted(by_canonical.items()), start=1):
        representative = max(group_items, key=lambda item: (item.digg_count, -item.time_sec))
        groups.append(
            ExpressionGroup(
                group_id=f"eg_{representative.video_id}_{index:04d}",
                video_id=representative.video_id,
                text=representative.clean_text,
                embedding_text=canonical,
                items=tuple(sorted(group_items, key=lambda item: (item.time_sec, item.comment_id))),
            )
        )
    return groups


def _peak_intervals(items: list[ExplorationDanmakuItem], *, peak_window_sec: float) -> list[dict[str, Any]]:
    if not items:
        return []
    sorted_items = sorted(items, key=lambda item: (item.time_sec, item.comment_id))
    raw_intervals: list[dict[str, Any]] = []
    for item in sorted_items:
        start_time = item.time_sec
        end_time = start_time + peak_window_sec
        interval_items = [candidate for candidate in sorted_items if start_time <= candidate.time_sec < end_time]
        raw_intervals.append(
            {
                "startTime": _round_time(start_time),
                "endTime": _round_time(end_time),
                "commentCount": len(interval_items),
                "sourceCommentIds": [candidate.comment_id for candidate in interval_items[:SOURCE_COMMENT_ID_LIMIT]],
            }
        )

    selected: list[dict[str, Any]] = []
    for interval in sorted(raw_intervals, key=lambda value: (-int(value["commentCount"]), float(value["startTime"]))):
        if any(min(float(interval["endTime"]), float(existing["endTime"])) > max(float(interval["startTime"]), float(existing["startTime"])) for existing in selected):
            continue
        selected.append(interval)
        if len(selected) >= PEAK_INTERVAL_LIMIT:
            break
    return sorted(selected, key=lambda value: float(value["startTime"]))


def _cluster_payload(
    *,
    video_id: str,
    cluster_index: int,
    groups: list[ExpressionGroup],
    peak_window_sec: float,
) -> dict[str, Any]:
    items = sorted(
        [item for group in groups for item in group.items],
        key=lambda item: (item.time_sec, item.comment_id),
    )
    text_counts = Counter(item.clean_text for item in items)
    ranked_groups = sorted(groups, key=lambda group: (-group.comment_count, -group.digg_sum, group.first_time_sec, group.text))
    examples = [
        {
            "text": group.text,
            "count": group.comment_count,
            "diggSum": group.digg_sum,
        }
        for group in ranked_groups[:EXAMPLE_TEXT_LIMIT]
    ]
    return {
        "clusterId": f"dsc_{video_id}_{cluster_index:03d}",
        "videoId": video_id,
        "commentCount": len(items),
        "uniqueTextCount": len(text_counts),
        "diggSum": sum(item.digg_count for item in items),
        "intentCounts": dict(Counter(classify_intent(item.clean_text, low_quality=item.low_quality) for item in items)),
        "examples": examples,
        "sourceCommentIds": [item.comment_id for item in items[:SOURCE_COMMENT_ID_LIMIT]],
        "peakIntervals": _peak_intervals(items, peak_window_sec=peak_window_sec),
    }


def _cluster_episode_groups(
    *,
    video_id: str,
    groups: list[ExpressionGroup],
    vectors: list[list[float]],
    similarity_threshold: float,
    min_cluster_comment_count: int,
    peak_window_sec: float,
    max_clusters_per_episode: int,
) -> list[dict[str, Any]]:
    components = _connected_components(vectors, threshold=similarity_threshold)
    clusters: list[dict[str, Any]] = []
    for component in components:
        component_groups = [groups[index] for index in component]
        comment_count = sum(group.comment_count for group in component_groups)
        if comment_count < min_cluster_comment_count:
            continue
        clusters.append(
            _cluster_payload(
                video_id=video_id,
                cluster_index=len(clusters) + 1,
                groups=component_groups,
                peak_window_sec=peak_window_sec,
            )
        )
    ranked_by_strength = sorted(
        clusters,
        key=lambda cluster: (
            -int(cluster["commentCount"]),
            -int(cluster["diggSum"]),
            float(cluster["peakIntervals"][0]["startTime"]) if cluster.get("peakIntervals") else 0.0,
            str(cluster["clusterId"]),
        ),
    )
    selected = sorted(
        ranked_by_strength[:max_clusters_per_episode],
        key=lambda cluster: (
            float(cluster["peakIntervals"][0]["startTime"]) if cluster.get("peakIntervals") else 0.0,
            -int(cluster["commentCount"]),
            -int(cluster["diggSum"]),
            str(cluster["clusterId"]),
        ),
    )
    for index, cluster in enumerate(selected, start=1):
        cluster["clusterId"] = f"dsc_{video_id}_{index:03d}"
    return selected


def _filter_items(
    items: list[ExplorationDanmakuItem],
    *,
    series_id: str | None,
    episode_id: str | None,
) -> list[ExplorationDanmakuItem]:
    filtered: list[ExplorationDanmakuItem] = []
    for item in items:
        if series_id and item.series_id != series_id:
            continue
        if episode_id and item.episode_id != episode_id:
            continue
        filtered.append(item)
    return filtered


def cluster_danmaku_semantics_from_csv(
    csv_path: Path,
    *,
    embedding_client: EmbeddingClientProtocol,
    series_id: str | None = None,
    episode_id: str | None = None,
    similarity_threshold: float = 0.82,
    min_cluster_comment_count: int = 3,
    peak_window_sec: float = 8.0,
    max_clusters_per_episode: int = 20,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    items, diagnostics = load_exploration_danmaku_csv(csv_path)
    filtered_items = _filter_items(items, series_id=series_id, episode_id=episode_id)
    items_by_video: dict[str, list[ExplorationDanmakuItem]] = defaultdict(list)
    for item in filtered_items:
        items_by_video[item.video_id].append(item)

    clusters: list[dict[str, Any]] = []
    embedding_calls: list[dict[str, Any]] = []
    if progress_callback is not None:
        progress_callback(
            "prepared",
            {
                "episode_count": len(items_by_video),
                "filtered_comment_count": len(filtered_items),
            },
        )
    for video_id, episode_items in sorted(items_by_video.items()):
        groups = _build_expression_groups(episode_items)
        if progress_callback is not None:
            progress_callback(
                "episode_start",
                {
                    "video_id": video_id,
                    "comment_count": len(episode_items),
                    "expression_group_count": len(groups),
                },
            )
        if not groups:
            continue
        if progress_callback is not None:
            progress_callback(
                "embedding_start",
                {
                    "video_id": video_id,
                    "expression_group_count": len(groups),
                },
            )
        vectors = embedding_client.embed_texts([group.embedding_text for group in groups])
        diagnostics_payload = getattr(embedding_client, "last_call_diagnostics", {})
        if isinstance(diagnostics_payload, dict):
            embedding_calls.append(dict(diagnostics_payload))
        if progress_callback is not None:
            progress_callback(
                "embedding_done",
                {
                    "video_id": video_id,
                    "vector_count": len(vectors),
                    "embedding_diagnostics": dict(diagnostics_payload) if isinstance(diagnostics_payload, dict) else {},
                },
            )
            progress_callback(
                "clustering_start",
                {
                    "video_id": video_id,
                    "vector_count": len(vectors),
                    "similarity_threshold": similarity_threshold,
                },
            )
        episode_clusters = _cluster_episode_groups(
            video_id=video_id,
            groups=groups,
            vectors=vectors,
            similarity_threshold=similarity_threshold,
            min_cluster_comment_count=min_cluster_comment_count,
            peak_window_sec=peak_window_sec,
            max_clusters_per_episode=max_clusters_per_episode,
        )
        clusters.extend(episode_clusters)
        if progress_callback is not None:
            progress_callback(
                "clustering_done",
                {
                    "video_id": video_id,
                    "cluster_count": len(episode_clusters),
                },
            )

    if progress_callback is not None:
        progress_callback(
            "completed",
            {
                "episode_count": len(items_by_video),
                "cluster_count": len(clusters),
            },
        )

    return {
        "createdAt": now_iso(),
        "sourceCsv": str(csv_path),
        "parameters": {
            "seriesId": series_id,
            "episodeId": episode_id,
            "similarityThreshold": similarity_threshold,
            "minClusterCommentCount": min_cluster_comment_count,
            "peakWindowSec": peak_window_sec,
            "maxClustersPerEpisode": max_clusters_per_episode,
        },
        "diagnostics": {
            "encoding": diagnostics.get("encoding"),
            "rawRowCount": diagnostics.get("raw_row_count", 0),
            "normalizedRowCount": diagnostics.get("normalized_row_count", 0),
            "skippedRowCount": diagnostics.get("skipped_row_count", 0),
            "skippedReasons": diagnostics.get("skipped_reasons", {}),
            "filteredCommentCount": len(filtered_items),
            "embeddingCalls": embedding_calls,
        },
        "episodeCount": len(items_by_video),
        "clusterCount": len(clusters),
        "clusters": clusters,
    }


def write_semantic_clusters_output(*, output_path: Path, payload: dict[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "cluster_danmaku_semantics_from_csv",
    "write_semantic_clusters_output",
]

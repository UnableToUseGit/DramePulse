from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from pipelines.client.embedding import EmbeddingClientProtocol
from pipelines.inner_voice_danmaku.exploration import (
    ExplorationDanmakuItem,
    classify_intent,
    load_exploration_danmaku_csv,
)

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


def _normalized_matrix(vectors: list[list[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def _hdbscan_components(
    vectors: list[list[float]],
    *,
    min_cluster_size: int,
    min_samples: int | None,
    cluster_selection_method: str,
) -> list[list[int]]:
    if not vectors:
        return []
    from sklearn.cluster import HDBSCAN

    normalized = _normalized_matrix(vectors)
    clusterer = HDBSCAN(
        min_cluster_size=max(2, int(min_cluster_size)),
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_method=cluster_selection_method,
        allow_single_cluster=False,
        copy=True,
    )
    labels = clusterer.fit_predict(normalized)
    components_by_label: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        if int(label) == -1:
            continue
        components_by_label[int(label)].append(index)
    return list(components_by_label.values())


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
    group_vectors: list[list[float]],
    peak_window_sec: float,
    representative_comment_count: int,
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
    peak_intervals = _peak_intervals(items, peak_window_sec=peak_window_sec)
    cluster_score = _cluster_score(
        comment_count=len(items),
        unique_text_count=len(text_counts),
        digg_sum=sum(item.digg_count for item in items),
        peak_intervals=peak_intervals,
    )
    return {
        "clusterId": f"dsc_{video_id}_{cluster_index:03d}",
        "videoId": video_id,
        "commentCount": len(items),
        "uniqueTextCount": len(text_counts),
        "diggSum": sum(item.digg_count for item in items),
        "clusterScore": cluster_score["score"],
        "scoreBreakdown": cluster_score["breakdown"],
        "intentCounts": dict(Counter(classify_intent(item.clean_text, low_quality=item.low_quality) for item in items)),
        "examples": examples,
        "representativeComments": _representative_comments(
            groups=groups,
            group_vectors=group_vectors,
            limit=representative_comment_count,
        ),
        "sourceCommentIds": [item.comment_id for item in items[:SOURCE_COMMENT_ID_LIMIT]],
        "peakIntervals": peak_intervals,
    }


def _cluster_score(
    *,
    comment_count: int,
    unique_text_count: int,
    digg_sum: int,
    peak_intervals: list[dict[str, Any]],
) -> dict[str, Any]:
    peak_count = max((int(interval["commentCount"]) for interval in peak_intervals), default=0)
    score = comment_count * 1.0 + unique_text_count * 0.35 + min(digg_sum, 100) * 0.08 + peak_count * 1.4
    return {
        "score": _round_time(score),
        "breakdown": {
            "commentCount": comment_count,
            "uniqueTextCount": unique_text_count,
            "diggSum": digg_sum,
            "peakCommentCount": peak_count,
        },
    }


def _representative_comments(
    *,
    groups: list[ExpressionGroup],
    group_vectors: list[list[float]],
    limit: int,
) -> list[dict[str, Any]]:
    if not groups or not group_vectors or limit <= 0:
        return []
    normalized = _normalized_matrix(group_vectors)
    centroid = normalized.mean(axis=0)
    centroid_norm = np.linalg.norm(centroid)
    if centroid_norm != 0.0:
        centroid = centroid / centroid_norm
    ranked: list[tuple[float, ExpressionGroup]] = []
    for index, group in enumerate(groups):
        distance = float(np.linalg.norm(normalized[index] - centroid))
        ranked.append((distance, group))
    representatives: list[dict[str, Any]] = []
    for distance, group in sorted(ranked, key=lambda value: (value[0], -value[1].comment_count, -value[1].digg_sum, value[1].first_time_sec))[:limit]:
        source_items = sorted(group.items, key=lambda item: (item.time_sec, item.comment_id))
        representatives.append(
            {
                "text": group.text,
                "count": group.comment_count,
                "diggSum": group.digg_sum,
                "distanceToCentroid": _round_time(distance),
                "sourceCommentIds": [item.comment_id for item in source_items[:SOURCE_COMMENT_ID_LIMIT]],
                "timeSec": _round_time(source_items[0].time_sec),
            }
        )
    return representatives


def _cluster_episode_groups(
    *,
    video_id: str,
    groups: list[ExpressionGroup],
    vectors: list[list[float]],
    cluster_method: str,
    similarity_threshold: float,
    min_cluster_comment_count: int,
    hdbscan_min_cluster_size: int,
    hdbscan_min_samples: int | None,
    hdbscan_cluster_selection_method: str,
    peak_window_sec: float,
    top_k_clusters: int,
    representative_comment_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if cluster_method == "connected_components":
        components = _connected_components(vectors, threshold=similarity_threshold)
    elif cluster_method == "hdbscan":
        components = _hdbscan_components(
            vectors,
            min_cluster_size=hdbscan_min_cluster_size,
            min_samples=hdbscan_min_samples,
            cluster_selection_method=hdbscan_cluster_selection_method,
        )
    else:
        raise ValueError(f"Unsupported cluster_method: {cluster_method}")
    clusters: list[dict[str, Any]] = []
    for component in components:
        component_groups = [groups[index] for index in component]
        component_vectors = [vectors[index] for index in component]
        comment_count = sum(group.comment_count for group in component_groups)
        if comment_count < min_cluster_comment_count:
            continue
        clusters.append(
            _cluster_payload(
                video_id=video_id,
                cluster_index=len(clusters) + 1,
                groups=component_groups,
                group_vectors=component_vectors,
                peak_window_sec=peak_window_sec,
                representative_comment_count=representative_comment_count,
            )
        )
    ranked_by_strength = sorted(
        clusters,
        key=lambda cluster: (
            -float(cluster["clusterScore"]),
            -int(cluster["commentCount"]),
            float(cluster["peakIntervals"][0]["startTime"]) if cluster.get("peakIntervals") else 0.0,
            str(cluster["clusterId"]),
        ),
    )
    all_clusters_by_score = [deepcopy(cluster) for cluster in ranked_by_strength]
    for index, cluster in enumerate(all_clusters_by_score, start=1):
        cluster["scoreRank"] = index
    selected_limit = max(0, int(top_k_clusters))
    selected = sorted(
        [deepcopy(cluster) for cluster in ranked_by_strength[:selected_limit]],
        key=lambda cluster: (
            float(cluster["peakIntervals"][0]["startTime"]) if cluster.get("peakIntervals") else 0.0,
            -float(cluster["clusterScore"]),
            str(cluster["clusterId"]),
        ),
    )
    for index, cluster in enumerate(selected, start=1):
        cluster["clusterId"] = f"dsc_{video_id}_{index:03d}"
    return selected, all_clusters_by_score


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
    cluster_method: str = "hdbscan",
    min_cluster_comment_count: int = 3,
    peak_window_sec: float = 8.0,
    max_clusters_per_episode: int = 20,
    top_k_clusters: int | None = None,
    representative_comment_count: int = 5,
    hdbscan_min_cluster_size: int = 5,
    hdbscan_min_samples: int | None = 3,
    hdbscan_cluster_selection_method: str = "eom",
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    items, diagnostics = load_exploration_danmaku_csv(csv_path)
    filtered_items = _filter_items(items, series_id=series_id, episode_id=episode_id)
    items_by_video: dict[str, list[ExplorationDanmakuItem]] = defaultdict(list)
    for item in filtered_items:
        items_by_video[item.video_id].append(item)

    clusters: list[dict[str, Any]] = []
    all_clusters_by_score: list[dict[str, Any]] = []
    embedding_calls: list[dict[str, Any]] = []
    raw_cluster_count = 0
    selected_top_k_clusters = max_clusters_per_episode if top_k_clusters is None else top_k_clusters
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
                    "cluster_method": cluster_method,
                    "similarity_threshold": similarity_threshold,
                    "hdbscan_min_cluster_size": hdbscan_min_cluster_size,
                    "hdbscan_min_samples": hdbscan_min_samples,
                    "hdbscan_cluster_selection_method": hdbscan_cluster_selection_method,
                    "top_k_clusters": selected_top_k_clusters,
                },
            )
        episode_clusters, episode_all_clusters_by_score = _cluster_episode_groups(
            video_id=video_id,
            groups=groups,
            vectors=vectors,
            cluster_method=cluster_method,
            similarity_threshold=similarity_threshold,
            min_cluster_comment_count=min_cluster_comment_count,
            hdbscan_min_cluster_size=hdbscan_min_cluster_size,
            hdbscan_min_samples=hdbscan_min_samples,
            hdbscan_cluster_selection_method=hdbscan_cluster_selection_method,
            peak_window_sec=peak_window_sec,
            top_k_clusters=selected_top_k_clusters,
            representative_comment_count=representative_comment_count,
        )
        raw_cluster_count += len(episode_all_clusters_by_score)
        clusters.extend(episode_clusters)
        all_clusters_by_score.extend(episode_all_clusters_by_score)
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

    all_clusters_by_score = sorted(
        all_clusters_by_score,
        key=lambda cluster: (
            -float(cluster["clusterScore"]),
            -int(cluster["commentCount"]),
            float(cluster["peakIntervals"][0]["startTime"]) if cluster.get("peakIntervals") else 0.0,
            str(cluster["clusterId"]),
        ),
    )
    for index, cluster in enumerate(all_clusters_by_score, start=1):
        cluster["scoreRank"] = index

    return {
        "createdAt": now_iso(),
        "sourceCsv": str(csv_path),
        "parameters": {
            "seriesId": series_id,
            "episodeId": episode_id,
            "clusterMethod": cluster_method,
            "similarityThreshold": similarity_threshold,
            "minClusterCommentCount": min_cluster_comment_count,
            "peakWindowSec": peak_window_sec,
            "maxClustersPerEpisode": max_clusters_per_episode,
            "topKClusters": selected_top_k_clusters,
            "representativeCommentCount": representative_comment_count,
            "hdbscanMinClusterSize": hdbscan_min_cluster_size,
            "hdbscanMinSamples": hdbscan_min_samples,
            "hdbscanClusterSelectionMethod": hdbscan_cluster_selection_method,
        },
        "diagnostics": {
            "encoding": diagnostics.get("encoding"),
            "rawRowCount": diagnostics.get("raw_row_count", 0),
            "normalizedRowCount": diagnostics.get("normalized_row_count", 0),
            "skippedRowCount": diagnostics.get("skipped_row_count", 0),
            "skippedReasons": diagnostics.get("skipped_reasons", {}),
            "filteredCommentCount": len(filtered_items),
            "rawClusterCount": raw_cluster_count,
            "embeddingCalls": embedding_calls,
        },
        "episodeCount": len(items_by_video),
        "clusterCount": len(clusters),
        "topClusters": clusters,
        "allClustersByScore": all_clusters_by_score,
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

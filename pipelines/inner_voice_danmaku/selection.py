from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines.client import LlmClientProtocol
from pipelines.story_chapter.baseline_text import (
    Utterance,
    format_utterance_timeline,
    load_utterances_from_transcription,
)

SOURCE_COMMENT_ID_LIMIT = 10
ProgressCallback = Callable[[str, dict[str, Any]], None]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _compact_text(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def _is_simple_emotion_text(text: str) -> bool:
    compact = _compact_text(text)
    if compact in {"哈哈", "哈哈哈", "哈哈哈哈", "哈哈哈哈哈", "爽", "啊啊啊", "笑死", "笑死了"}:
        return True
    return bool(compact) and all(char in {"哈", "啊", "爽", "？", "?", "!", "！"} for char in compact)


def _cluster_source_ids(cluster: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []
    for comment in cluster.get("representativeComments") or []:
        if not isinstance(comment, dict):
            continue
        source_ids.extend(str(value) for value in comment.get("sourceCommentIds") or [])
    for value in cluster.get("sourceCommentIds") or []:
        source_ids.append(str(value))
    seen: set[str] = set()
    unique: list[str] = []
    for source_id in source_ids:
        if source_id in seen:
            continue
        seen.add(source_id)
        unique.append(source_id)
    return unique


def _prompt_cluster(
    cluster: dict[str, Any],
    *,
    representative_comment_count: int,
    example_count: int,
) -> dict[str, Any]:
    representatives = [
        {
            "text": _clean_text(comment.get("text")),
            "sourceCommentIds": [str(value) for value in comment.get("sourceCommentIds") or []][:SOURCE_COMMENT_ID_LIMIT],
        }
        for comment in cluster.get("representativeComments") or []
        if isinstance(comment, dict) and _clean_text(comment.get("text"))
    ][:representative_comment_count]
    examples = [
        _clean_text(example.get("text"))
        for example in cluster.get("examples") or []
        if isinstance(example, dict) and _clean_text(example.get("text"))
    ][:example_count]
    peak_intervals = []
    for interval in cluster.get("peakIntervals") or []:
        if not isinstance(interval, dict):
            continue
        peak_intervals.append(
            {
                "startTime": interval.get("startTime"),
                "endTime": interval.get("endTime"),
                "commentCount": interval.get("commentCount"),
            }
        )
    return {
        "clusterId": cluster.get("clusterId"),
        "scoreRank": cluster.get("scoreRank"),
        "clusterScore": cluster.get("clusterScore"),
        "commentCount": cluster.get("commentCount"),
        "uniqueTextCount": cluster.get("uniqueTextCount"),
        "diggSum": cluster.get("diggSum"),
        "peakIntervals": peak_intervals,
        "representativeComments": representatives,
        "examples": examples,
        "sourceCommentIds": _cluster_source_ids(cluster)[:SOURCE_COMMENT_ID_LIMIT],
    }


def _ranked_clusters(payload: dict[str, Any]) -> list[dict[str, Any]]:
    clusters = payload.get("allClustersByScore")
    if not isinstance(clusters, list):
        clusters = payload.get("topClusters")
    if not isinstance(clusters, list):
        clusters = payload.get("clusters")
    if not isinstance(clusters, list):
        return []
    return [cluster for cluster in clusters if isinstance(cluster, dict)]


def build_inner_voice_selection_prompt(
    *,
    video_id: str,
    utterances: Sequence[Utterance],
    clusters: Sequence[dict[str, Any]],
    top_cluster_count: int = 50,
    representative_comment_count: int = 3,
    example_count: int = 0,
) -> str:
    prompt_clusters = [
        _prompt_cluster(
            cluster,
            representative_comment_count=representative_comment_count,
            example_count=example_count,
        )
        for cluster in clusters[:top_cluster_count]
    ]
    payload = {
        "videoId": video_id,
        "topClusterCount": top_cluster_count,
        "selectionGoal": "从全剧 top clusters 中选出 1-3 个最适合被改写成心里话弹幕的语义簇，并为每个生成一条可直接发送的中文弹幕文案。",
        "clusters": prompt_clusters,
    }
    return "\n".join(
        [
            "# 角色",
            "你是短剧播放器里的“心里话弹幕”文案选择器。",
            "",
            "# 产品背景",
            "心里话弹幕是一种低摩擦互动：系统会在合适时机预先生成一条弹幕胶囊，用户不需要打字，只要轻轻上推就能发送。",
            "它不是剧情总结，不是评论区长评，也不是情绪按钮。它的价值是帮用户快速发出一句“我也想这么说”的弹幕。",
            "",
            "# 为什么有这些弹幕簇",
            "每个弹幕簇来自真实观众弹幕的语义聚类。",
            "一个簇里有大量相似弹幕，说明这段剧情唤起了很多观众相似的表达欲。",
            "因此，弹幕簇代表观众很有可能想发送相关语义的弹幕。",
            "你的任务是判断：哪些簇最适合被改写成“用户可能也想发”的心里话弹幕。",
            "",
            "# 输入",
            "你会收到两类信息：",
            "1. 整集字幕：用于理解短剧剧情、人物关系和语境。",
            "2. 候选语义簇：来自全剧真实弹幕聚类，每个 cluster 包含分数、弹幕数量、峰值区间、靠近中心的代表弹幕。",
            "",
            "# 任务",
            "只从输入 clusters 中选择 1-3 个最适合作为心里话弹幕的簇。",
            "为每个被选中的簇生成一条用户可一推发送的短中文弹幕。",
            "不要输出 triggerTime、durationSec 或任何触发时间；这一步不负责时间决策。",
            "",
            "# 选择标准",
            "优先选择：",
            "- 观众可直接代入发送的观点、态度或感慨。",
            "- 对角色、演员魅力、人物关系、剧情反转、台词梗的自然表达。",
            "- 有共鸣、有梗，但不依赖复杂解释。",
            "- 文案短，像真实用户会发的弹幕。",
            "",
            "排除：",
            "- 纯名词复读，例如“二哥”“甘蔗”。",
            "- 简单情绪，例如“哈哈哈”“爽”“哭了”。",
            "- 纯表情或纯标点。",
            "- 对平台、演员阵容、二刷、拍摄地等过于元信息的评论，除非它明显适合当用户即时弹幕。",
            "- 太像剧情总结、宣传语或评论区长评的表达。",
            "",
            "# 改写规则",
            "- 可以轻微改写，但不能脱离 cluster 原意。",
            "- 文案要像用户随手发出的弹幕。",
            "- 建议 4-18 个中文字符。",
            "- 每个 selected.clusterId 必须来自输入 clusters。",
            "- sourceCommentIds 如果输出，必须来自该 cluster 的 sourceCommentIds 或 representativeComments.sourceCommentIds。",
            "",
            "# 输出格式",
            "只输出 JSON，不要输出 Markdown 或解释文字。",
            "JSON 格式：",
            "{\"selected\":[{\"clusterId\":\"...\",\"text\":\"...\",\"suitabilityScore\":0.0,\"reason\":\"...\",\"sourceCommentIds\":[\"...\"]}]}",
            "",
            "## 整集字幕",
            format_utterance_timeline(utterances),
            "",
            "## 候选语义簇",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def build_system_prompt() -> str:
    return "Return only valid JSON. Do not include markdown. Do not output triggerTime."


def _diagnostic_total_tokens(diagnostics: Any) -> int | None:
    if not isinstance(diagnostics, dict):
        return None
    usage = diagnostics.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        return int(usage.get("total_tokens"))
    except (TypeError, ValueError):
        return None


def _parse_selected_candidates(
    *,
    raw_result: dict[str, Any],
    clusters_by_id: dict[str, dict[str, Any]],
    video_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = raw_result.get("selected")
    if not isinstance(selected, list):
        return [], []
    candidates: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for raw_candidate in selected:
        if not isinstance(raw_candidate, dict):
            continue
        cluster_id = str(raw_candidate.get("clusterId") or "")
        text = _clean_text(raw_candidate.get("text"))
        reason = _clean_text(raw_candidate.get("reason"))
        try:
            suitability_score = float(raw_candidate.get("suitabilityScore") or 0.0)
        except (TypeError, ValueError):
            suitability_score = 0.0
        source_comment_ids = [str(value) for value in raw_candidate.get("sourceCommentIds") or []]
        reject_reason = ""
        if cluster_id not in clusters_by_id:
            reject_reason = "unknown_cluster_id"
        elif not text:
            reject_reason = "empty_text"
        elif _is_simple_emotion_text(text):
            reject_reason = "simple_emotion_text"
        elif not 0.0 <= suitability_score <= 1.0:
            reject_reason = "invalid_suitability_score"
        if reject_reason:
            filtered.append(
                {
                    "clusterId": cluster_id,
                    "text": text,
                    "suitabilityScore": suitability_score,
                    "reason": reject_reason,
                }
            )
            continue
        cluster = clusters_by_id[cluster_id]
        candidates.append(
            {
                "candidateId": f"ivcluster_{video_id}_{len(candidates) + 1:03d}",
                "videoId": video_id,
                "clusterId": cluster_id,
                "text": text,
                "suitabilityScore": _round_time(suitability_score),
                "reason": reason,
                "sourceCommentIds": source_comment_ids[:SOURCE_COMMENT_ID_LIMIT],
                "cluster": {
                    "scoreRank": cluster.get("scoreRank"),
                    "clusterScore": cluster.get("clusterScore"),
                    "commentCount": cluster.get("commentCount"),
                    "uniqueTextCount": cluster.get("uniqueTextCount"),
                    "peakIntervals": cluster.get("peakIntervals") or [],
                    "representativeComments": cluster.get("representativeComments") or [],
                    "examples": cluster.get("examples") or [],
                },
            }
        )
    return candidates[:3], filtered


def _video_id_from_payload(payload: dict[str, Any], *, fallback: str) -> str:
    for cluster in _ranked_clusters(payload):
        video_id = _clean_text(cluster.get("videoId"))
        if video_id:
            return video_id
    params = payload.get("parameters")
    if isinstance(params, dict):
        series_id = _clean_text(params.get("seriesId"))
        episode_id = _clean_text(params.get("episodeId"))
        if series_id and episode_id:
            return f"{series_id}_{episode_id}"
    return fallback


def select_inner_voice_candidates_from_semantic_clusters(
    semantic_payload: dict[str, Any],
    *,
    transcription_path: Path,
    llm_client: LlmClientProtocol,
    top_cluster_count: int = 50,
    representative_comment_count: int = 3,
    example_count: int = 0,
    max_tokens: int = 4000,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    utterances = load_utterances_from_transcription(transcription_path)
    clusters = _ranked_clusters(semantic_payload)[:top_cluster_count]
    video_id = _video_id_from_payload(semantic_payload, fallback=transcription_path.parent.name)
    if progress_callback is not None:
        progress_callback(
            "prepared",
            {
                "video_id": video_id,
                "utterance_count": len(utterances),
                "cluster_count": len(clusters),
                "top_cluster_count": top_cluster_count,
            },
        )
        progress_callback("llm_start", {"video_id": video_id, "cluster_count": len(clusters), "max_tokens": max_tokens})
    raw_result = llm_client.generate_json_multimodal(
        system_prompt=build_system_prompt(),
        user_prompt=build_inner_voice_selection_prompt(
            video_id=video_id,
            utterances=utterances,
            clusters=clusters,
            top_cluster_count=top_cluster_count,
            representative_comment_count=representative_comment_count,
            example_count=example_count,
        ),
        image_paths=[],
        frame_timestamps_seconds=[],
        max_tokens=max_tokens,
    )
    diagnostics = getattr(llm_client, "last_call_diagnostics", {})
    clusters_by_id = {str(cluster.get("clusterId")): cluster for cluster in clusters if cluster.get("clusterId")}
    candidates, filtered = _parse_selected_candidates(raw_result=raw_result, clusters_by_id=clusters_by_id, video_id=video_id)
    total_tokens = _diagnostic_total_tokens(diagnostics)
    if progress_callback is not None:
        progress_callback(
            "llm_done",
            {
                "video_id": video_id,
                "candidate_count": len(candidates),
                "filtered_count": len(filtered),
                "total_tokens": total_tokens,
            },
        )
        progress_callback(
            "completed",
            {"video_id": video_id, "candidate_count": len(candidates), "filtered_count": len(filtered)},
        )
    return {
        "createdAt": now_iso(),
        "sourceSemanticClusters": semantic_payload.get("sourceCsv") or semantic_payload.get("sourceSemanticClusters"),
        "sourceTranscription": str(transcription_path),
        "videoId": video_id,
        "topClusterCount": top_cluster_count,
        "utteranceCount": len(utterances),
        "candidateCount": len(candidates),
        "candidates": candidates,
        "debug": {
            "llmRawResult": raw_result,
            "filteredSelections": filtered,
            "llmCalls": [dict(diagnostics) if isinstance(diagnostics, dict) else {}],
        },
    }


def load_semantic_clusters_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_inner_voice_selection_output(*, output_path: Path, payload: dict[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "build_inner_voice_selection_prompt",
    "load_semantic_clusters_payload",
    "select_inner_voice_candidates_from_semantic_clusters",
    "write_inner_voice_selection_output",
]

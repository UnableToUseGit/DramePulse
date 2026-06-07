from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from pipelines.client import LlmClientProtocol


SUPPORTED_CLUSTER_TYPES = {"actor_charm", "scene_commentary", "meme", "other"}
SIMPLE_EMOTION_TEXTS = {"哈哈", "哈哈哈", "哈哈哈哈", "爽", "啊啊啊", "笑死", "笑死了", "哭了"}


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
    if compact in SIMPLE_EMOTION_TEXTS:
        return True
    return bool(compact) and all(char in {"哈", "啊", "爽", "？", "?"} for char in compact)


def _window_comments(window: dict[str, Any]) -> list[dict[str, Any]]:
    comments = window.get("comments")
    if not isinstance(comments, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, raw_comment in enumerate(comments, start=1):
        if not isinstance(raw_comment, dict):
            continue
        text = _clean_text(raw_comment.get("text") or raw_comment.get("clean_text"))
        if not text:
            continue
        try:
            time_sec = float(raw_comment.get("time_sec") or 0.0)
        except (TypeError, ValueError):
            time_sec = 0.0
        try:
            digg_count = int(float(raw_comment.get("digg_count") or 0))
        except (TypeError, ValueError):
            digg_count = 0
        normalized.append(
            {
                "commentId": str(raw_comment.get("comment_id") or raw_comment.get("commentId") or f"comment_{index}"),
                "timeSec": _round_time(time_sec),
                "text": text,
                "diggCount": max(0, digg_count),
            }
        )
    return sorted(normalized, key=lambda comment: (float(comment["timeSec"]), str(comment["commentId"])))


def build_window_semantic_prompt(window: dict[str, Any]) -> str:
    payload = {
        "windowId": window.get("window_id") or window.get("windowId"),
        "videoId": window.get("video_id") or window.get("videoId"),
        "startTime": window.get("start_time") or window.get("startTime"),
        "endTime": window.get("end_time") or window.get("endTime"),
        "resonanceScore": window.get("resonance_score") or window.get("resonanceScore"),
        "actorCharmRatio": window.get("actor_charm_ratio") or window.get("actorCharmRatio"),
        "emotionBurstRatio": window.get("emotion_burst_ratio") or window.get("emotionBurstRatio"),
        "comments": _window_comments(window),
    }
    return "\n".join(
        [
            "你是短剧心里话弹幕语义簇判断器。",
            "任务：判断这个时间窗口内是否存在同语义弹幕簇，并抽取或轻微改写一条适合用户一推发送的心里话弹幕。",
            "只基于输入 comments 判断，不要凭空生成。每个 sourceCommentIds 必须来自输入 commentId。",
            "不要输出简单情绪表达，例如哈哈哈、爽、啊啊啊、纯表情。",
            "优先选择演员/角色魅力、具体剧情/角色评价、玩梗等有表达内容的弹幕。",
            "返回 JSON：{\"usable\":true|false,\"clusters\":[{\"clusterType\":\"actor_charm|scene_commentary|meme|other\",\"representativeText\":\"...\",\"sourceCommentIds\":[\"...\"],\"confidence\":0.0,\"reason\":\"...\"}]}",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _build_system_prompt() -> str:
    return "Return only valid JSON. Do not include markdown."


def _windows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    windows = payload.get("windows")
    if not isinstance(windows, list):
        windows = payload.get("resonance_windows")
    if not isinstance(windows, list):
        return []
    return [window for window in windows if isinstance(window, dict)]


def _parse_llm_clusters(
    *,
    raw_result: dict[str, Any],
    window: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if raw_result.get("usable") is False:
        return [], []
    raw_clusters = raw_result.get("clusters")
    if not isinstance(raw_clusters, list):
        return [], []
    comments = _window_comments(window)
    valid_comment_ids = {str(comment["commentId"]) for comment in comments}
    time_by_comment_id = {str(comment["commentId"]): float(comment["timeSec"]) for comment in comments}
    candidates: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for raw_cluster in raw_clusters:
        if not isinstance(raw_cluster, dict):
            continue
        cluster_type = str(raw_cluster.get("clusterType") or "")
        text = _clean_text(raw_cluster.get("representativeText"))
        source_ids = [str(value) for value in raw_cluster.get("sourceCommentIds") or []]
        try:
            confidence = float(raw_cluster.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        reason = _clean_text(raw_cluster.get("reason"))
        reject_reason = ""
        if cluster_type not in SUPPORTED_CLUSTER_TYPES:
            reject_reason = "unsupported_cluster_type"
        elif not text:
            reject_reason = "empty_text"
        elif _is_simple_emotion_text(text):
            reject_reason = "simple_emotion_text"
        elif not source_ids or any(source_id not in valid_comment_ids for source_id in source_ids):
            reject_reason = "invalid_source_comment_ids"
        elif confidence < 0.65:
            reject_reason = "low_confidence"
        if reject_reason:
            filtered.append(
                {
                    "window_id": window.get("window_id") or window.get("windowId"),
                    "cluster_type": cluster_type,
                    "text": text,
                    "source_comment_ids": source_ids,
                    "reason": reject_reason,
                }
            )
            continue
        candidates.append(
            {
                "window_id": window.get("window_id") or window.get("windowId"),
                "video_id": window.get("video_id") or window.get("videoId"),
                "trigger_time": _round_time(min(time_by_comment_id[source_id] for source_id in source_ids)),
                "text": text,
                "cluster_type": cluster_type,
                "source_comment_ids": source_ids,
                "confidence": _round_time(confidence),
                "reason": reason,
            }
        )
    return candidates, filtered


def refine_danmaku_windows_with_llm(
    payload: dict[str, Any],
    *,
    llm_client: LlmClientProtocol,
    max_tokens: int = 1200,
    duration_sec: float = 5.0,
) -> dict[str, Any]:
    windows = _windows_from_payload(payload)
    candidates: list[dict[str, Any]] = []
    filtered_clusters: list[dict[str, Any]] = []
    llm_calls: list[dict[str, Any]] = []
    for window in windows:
        raw_result = llm_client.generate_json_multimodal(
            system_prompt=_build_system_prompt(),
            user_prompt=build_window_semantic_prompt(window),
            image_paths=[],
            frame_timestamps_seconds=[],
            max_tokens=max_tokens,
        )
        diagnostics = getattr(llm_client, "last_call_diagnostics", {})
        llm_calls.append(dict(diagnostics) if isinstance(diagnostics, dict) else {})
        window_candidates, window_filtered = _parse_llm_clusters(raw_result=raw_result, window=window)
        filtered_clusters.extend(window_filtered)
        for candidate in window_candidates:
            candidate_id = f"ivllm_{candidate['video_id']}_{len(candidates) + 1:03d}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    **candidate,
                    "duration_sec": _round_time(duration_sec),
                }
            )
    return {
        "createdAt": now_iso(),
        "sourceCsv": payload.get("source_csv") or payload.get("sourceCsv"),
        "llmWindowCount": len(windows),
        "candidateCount": len(candidates),
        "candidates": candidates,
        "debug": {
            "filteredClusterCount": len(filtered_clusters),
            "filteredClusters": filtered_clusters,
            "llmCalls": llm_calls,
        },
    }


def load_windows_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_llm_candidates_output(*, output_path: Path, payload: dict[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "build_window_semantic_prompt",
    "load_windows_payload",
    "refine_danmaku_windows_with_llm",
    "write_llm_candidates_output",
]

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
from pathlib import Path
from typing import Any, Callable

from pipelines.client import LlmClientProtocol


SUPPORTED_LLM_INTENTS = {"plot_reaction", "meme"}
SUPPORTED_INTENTS = {"actor_charm", *SUPPORTED_LLM_INTENTS}

ACTOR_CHARM_KEYWORDS = (
    "帅",
    "美",
    "漂亮",
    "好看",
    "颜值",
    "气质",
    "眼神",
    "表情",
    "演技",
    "哭戏",
    "老公",
    "老婆",
    "姐姐",
    "妹妹",
    "小奶狗",
    "绝了",
    "鲨我",
    "顶不住",
)

GENERIC_LOW_SEMANTIC_TEXTS = {
    "哈哈",
    "哈哈哈",
    "哈哈哈哈",
    "哈哈哈哈哈",
    "爽",
    "笑死",
    "哭了",
    "甜",
}

ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class InnerVoiceDanmakuItem:
    comment_id: str
    time_sec: float
    text: str
    digg_count: int


@dataclass(frozen=True)
class CandidateWindow:
    window_id: str
    start_time: float
    end_time: float
    items: tuple[InnerVoiceDanmakuItem, ...]
    score: float


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _compact_text(value: str) -> str:
    return "".join(value.split()).lower()


def _is_low_quality_text(text: str) -> bool:
    compact = _compact_text(text)
    if not compact:
        return True
    if len(compact) > 24:
        return True
    if compact in GENERIC_LOW_SEMANTIC_TEXTS:
        return True
    if re.fullmatch(r"[\W_]+", compact):
        return True
    if re.fullmatch(r"\d+", compact):
        return True
    if re.fullmatch(r"(哈|笑|啊|？|\?)+", compact):
        return True
    return False


def _normalize_danmaku_items(items: list[dict[str, Any]]) -> list[InnerVoiceDanmakuItem]:
    normalized: list[InnerVoiceDanmakuItem] = []
    for index, raw_item in enumerate(items):
        text = _clean_text(raw_item.get("text") or raw_item.get("content"))
        if _is_low_quality_text(text):
            continue
        try:
            if raw_item.get("time_sec") is not None:
                time_sec = float(raw_item["time_sec"])
            elif raw_item.get("time_ms") is not None:
                time_sec = float(raw_item["time_ms"]) / 1000.0
            else:
                continue
        except (TypeError, ValueError):
            continue
        if time_sec < 0:
            continue
        try:
            digg_count = int(float(raw_item.get("digg_count") or raw_item.get("like_count") or 0))
        except (TypeError, ValueError):
            digg_count = 0
        comment_id = str(
            raw_item.get("danmaku_id")
            or raw_item.get("comment_id")
            or raw_item.get("id")
            or f"dm_{index + 1}"
        )
        normalized.append(
            InnerVoiceDanmakuItem(
                comment_id=comment_id,
                time_sec=_round_time(time_sec),
                text=text,
                digg_count=max(0, digg_count),
            )
        )
    return sorted(normalized, key=lambda item: (item.time_sec, item.comment_id))


def _window_score(items: list[InnerVoiceDanmakuItem]) -> float:
    text_counts = Counter(item.text for item in items)
    unique_text_count = len(text_counts)
    repeat_text_count = max(text_counts.values(), default=0)
    repeat_score = max(0, repeat_text_count - 1) * 0.75
    like_score = min(sum(item.digg_count for item in items), 30) * 0.1
    return _round_time(len(items) + repeat_score + unique_text_count * 0.25 + like_score)


def _build_candidate_windows(
    *,
    video_id: str,
    items: list[InnerVoiceDanmakuItem],
    window_sec: float,
    step_sec: float,
    min_window_danmaku_count: int,
    min_unique_text_count: int,
    min_window_score: float,
) -> list[CandidateWindow]:
    if not items or window_sec <= 0 or step_sec <= 0:
        return []

    raw_windows: list[CandidateWindow] = []
    start_time = items[0].time_sec
    last_time = items[-1].time_sec
    index = 0
    while start_time <= last_time:
        end_time = start_time + window_sec
        while index < len(items) and items[index].time_sec < start_time:
            index += 1
        scan_index = index
        window_items: list[InnerVoiceDanmakuItem] = []
        while scan_index < len(items) and items[scan_index].time_sec < end_time:
            window_items.append(items[scan_index])
            scan_index += 1
        score = _window_score(window_items)
        if (
            len(window_items) >= min_window_danmaku_count
            and score >= min_window_score
        ):
            raw_windows.append(
                CandidateWindow(
                    window_id=f"ivw_{video_id}_{len(raw_windows) + 1:03d}",
                    start_time=_round_time(start_time),
                    end_time=_round_time(end_time),
                    items=tuple(window_items),
                    score=score,
                )
            )
        start_time = _round_time(start_time + step_sec)

    selected: list[CandidateWindow] = []
    for window in sorted(raw_windows, key=lambda value: (-value.score, value.start_time)):
        if any(_windows_overlap(window, existing) for existing in selected):
            continue
        selected.append(window)
    return sorted(selected, key=lambda value: value.start_time)


def _windows_overlap(left: CandidateWindow, right: CandidateWindow) -> bool:
    return min(left.end_time, right.end_time) > max(left.start_time, right.start_time)


def _item_to_prompt_comment(item: InnerVoiceDanmakuItem) -> dict[str, Any]:
    return {
        "commentId": item.comment_id,
        "timeSec": item.time_sec,
        "text": item.text,
        "diggCount": item.digg_count,
    }


def _top_window_comments(window: CandidateWindow, *, limit: int = 40) -> list[dict[str, Any]]:
    sorted_items = sorted(window.items, key=lambda item: (-item.digg_count, item.time_sec, item.comment_id))
    return [_item_to_prompt_comment(item) for item in sorted_items[:limit]]


def build_inner_voice_prompt(
    *,
    video_id: str,
    window: dict[str, Any],
    subtitle_context: str = "",
) -> str:
    comments = window.get("topComments") if isinstance(window.get("topComments"), list) else []
    payload = {
        "videoId": video_id,
        "window": {
            "windowId": window.get("windowId"),
            "startTime": window.get("startTime"),
            "endTime": window.get("endTime"),
            "topComments": comments,
        },
        "subtitleContext": subtitle_context,
    }
    return "\n".join(
        [
            "You identify high-semantic inner voice danmaku clusters for a short-drama player.",
            "Only identify plot_reaction and meme. Do not output actor_charm, prediction, stance, complaint, or cp_reading.",
            "Use only the provided comments as evidence. Every sourceCommentIds entry must come from input commentId values.",
            "Each cluster must contain one representativeText, 6-18 Chinese characters preferred, like a real danmaku.",
            "Return JSON object: {\"clusters\":[{\"intentType\":\"plot_reaction|meme\",\"representativeText\":\"...\",\"sourceCommentIds\":[\"...\"],\"confidence\":0.0,\"reason\":\"...\"}]}",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def _build_system_prompt() -> str:
    return "You are a precise short-drama danmaku semantic clustering engine. Return only JSON."


def _actor_charm_score(item: InnerVoiceDanmakuItem) -> float:
    compact = _compact_text(item.text)
    keyword_hits = sum(1 for keyword in ACTOR_CHARM_KEYWORDS if keyword.lower() in compact)
    if keyword_hits <= 0:
        return 0.0
    specificity = 1.0 if any(keyword in compact for keyword in ("眼神", "表情", "演技", "哭戏", "气质")) else 0.0
    length_bonus = 1.0 if 6 <= len(compact) <= 18 else 0.0
    return keyword_hits * 2.0 + specificity + length_bonus + min(item.digg_count, 20) * 0.2


def _build_actor_charm_candidate(window: CandidateWindow) -> dict[str, Any] | None:
    groups: dict[str, list[InnerVoiceDanmakuItem]] = {}
    for item in window.items:
        score = _actor_charm_score(item)
        if score <= 0:
            continue
        groups.setdefault(item.text, []).append(item)
    if not groups:
        return None

    def group_score(group: list[InnerVoiceDanmakuItem]) -> float:
        representative = max(group, key=lambda item: (_actor_charm_score(item), item.digg_count, -item.time_sec))
        repeat_bonus = max(0, len(group) - 1) * 0.75
        like_bonus = min(sum(item.digg_count for item in group), 20) * 0.2
        return _actor_charm_score(representative) + repeat_bonus + like_bonus

    selected_items = max(groups.values(), key=lambda group: (group_score(group), len(group), -min(item.time_sec for item in group)))
    item = max(selected_items, key=lambda value: (_actor_charm_score(value), value.digg_count, -value.time_sec))
    score = group_score(selected_items)
    return {
        "intentType": "actor_charm",
        "representativeText": item.text,
        "sourceCommentIds": [source_item.comment_id for source_item in sorted(selected_items, key=lambda value: value.time_sec)],
        "confidence": min(0.99, 0.6 + score / 20.0),
        "reason": "规则命中角色魅力表达。",
        "triggerTime": min(source_item.time_sec for source_item in selected_items),
        "windowId": window.window_id,
        "score": _round_time(window.score + score),
    }


def _parse_llm_clusters(
    *,
    raw_result: dict[str, Any],
    window: CandidateWindow,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clusters = raw_result.get("clusters")
    if not isinstance(clusters, list):
        return [], []
    valid_comment_ids = {item.comment_id for item in window.items}
    time_by_comment_id = {item.comment_id: item.time_sec for item in window.items}
    candidates: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for raw_cluster in clusters:
        if not isinstance(raw_cluster, dict):
            continue
        intent_type = str(raw_cluster.get("intentType") or "")
        text = _clean_text(raw_cluster.get("representativeText"))
        source_ids = [str(value) for value in raw_cluster.get("sourceCommentIds") or []]
        try:
            confidence = float(raw_cluster.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        reason = _clean_text(raw_cluster.get("reason"))
        reject_reason = ""
        if intent_type not in SUPPORTED_LLM_INTENTS:
            reject_reason = "unsupported_intent"
        elif not text or _is_low_quality_text(text):
            reject_reason = "low_quality_text"
        elif not source_ids or any(source_id not in valid_comment_ids for source_id in source_ids):
            reject_reason = "invalid_source_comment_ids"
        elif confidence < 0.65:
            reject_reason = "low_confidence"
        if reject_reason:
            filtered.append(
                {
                    "intentType": intent_type,
                    "representativeText": text,
                    "sourceCommentIds": source_ids,
                    "reason": reject_reason,
                }
            )
            continue
        candidates.append(
            {
                "intentType": intent_type,
                "representativeText": text,
                "sourceCommentIds": source_ids,
                "confidence": confidence,
                "reason": reason,
                "triggerTime": min(time_by_comment_id[source_id] for source_id in source_ids),
                "windowId": window.window_id,
                "score": _round_time(window.score + confidence * 5.0 + len(source_ids)),
            }
        )
    return candidates, filtered


def _candidate_to_cue(
    *,
    video_id: str,
    candidate: dict[str, Any],
    index: int,
    duration_sec: float,
) -> dict[str, Any]:
    cue_id = f"iv_{video_id}_{index:03d}"
    return {
        "cueId": cue_id,
        "videoId": video_id,
        "highlightId": cue_id,
        "triggerTime": _round_time(float(candidate["triggerTime"])),
        "durationSec": _round_time(duration_sec),
        "text": str(candidate["representativeText"]),
        "danmakuTrack": (index - 1) % 3,
    }


def _select_final_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_cues_per_episode: int,
    min_gap_sec: float,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for candidate in sorted(candidates, key=lambda value: (-float(value.get("score", 0.0)), float(value["triggerTime"]))):
        text = str(candidate["representativeText"])
        if text in seen_texts:
            continue
        trigger_time = float(candidate["triggerTime"])
        if any(abs(trigger_time - float(existing["triggerTime"])) < min_gap_sec for existing in selected):
            continue
        selected.append(candidate)
        seen_texts.add(text)
        if len(selected) >= max_cues_per_episode:
            break
    return sorted(selected, key=lambda value: float(value["triggerTime"]))


class InnerVoiceDanmakuPipeline:
    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol | None = None,
        enable_llm_semantic: bool = False,
        window_sec: float = 8.0,
        step_sec: float = 2.0,
        min_window_danmaku_count: int = 4,
        min_unique_text_count: int = 2,
        min_window_score: float = 6.0,
        max_cues_per_episode: int = 8,
        duration_sec: float = 5.0,
        min_cue_gap_sec: float = 12.0,
        llm_max_tokens: int = 1200,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.enable_llm_semantic = enable_llm_semantic
        self.window_sec = window_sec
        self.step_sec = step_sec
        self.min_window_danmaku_count = min_window_danmaku_count
        self.min_unique_text_count = min_unique_text_count
        self.min_window_score = min_window_score
        self.max_cues_per_episode = max_cues_per_episode
        self.duration_sec = duration_sec
        self.min_cue_gap_sec = min_cue_gap_sec
        self.llm_max_tokens = llm_max_tokens
        self.progress_callback = progress_callback
        self.last_llm_calls: list[dict[str, Any]] = []

    def _emit_progress(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_callback is not None:
            self.progress_callback(event, payload)

    def run(
        self,
        *,
        video_id: str,
        series_id: str,
        episode_id: str,
        danmaku_items: list[dict[str, Any]],
        subtitle_context_by_window: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        normalized_items = _normalize_danmaku_items(danmaku_items)
        self._emit_progress(
            "prepared",
            {
                "video_id": video_id,
                "source_danmaku_count": len(danmaku_items),
                "clean_danmaku_count": len(normalized_items),
            },
        )
        windows = _build_candidate_windows(
            video_id=video_id,
            items=normalized_items,
            window_sec=self.window_sec,
            step_sec=self.step_sec,
            min_window_danmaku_count=self.min_window_danmaku_count,
            min_unique_text_count=self.min_unique_text_count,
            min_window_score=self.min_window_score,
        )
        self._emit_progress(
            "windows_built",
            {
                "video_id": video_id,
                "candidate_window_count": len(windows),
            },
        )

        candidates: list[dict[str, Any]] = []
        filtered_candidates: list[dict[str, Any]] = []
        self.last_llm_calls = []
        subtitle_context_by_window = subtitle_context_by_window or {}
        for window in windows:
            actor_candidate = _build_actor_charm_candidate(window)
            if actor_candidate is not None:
                candidates.append(actor_candidate)
            if self.enable_llm_semantic and self.llm_client is not None:
                prompt_window = {
                    "windowId": window.window_id,
                    "startTime": window.start_time,
                    "endTime": window.end_time,
                    "topComments": _top_window_comments(window),
                }
                raw_result = self.llm_client.generate_json_multimodal(
                    system_prompt=_build_system_prompt(),
                    user_prompt=build_inner_voice_prompt(
                        video_id=video_id,
                        window=prompt_window,
                        subtitle_context=subtitle_context_by_window.get(window.window_id, ""),
                    ),
                    image_paths=[],
                    frame_timestamps_seconds=[],
                    max_tokens=self.llm_max_tokens,
                )
                diagnostics = getattr(self.llm_client, "last_call_diagnostics", {})
                self.last_llm_calls.append(dict(diagnostics) if isinstance(diagnostics, dict) else {})
                llm_candidates, llm_filtered = _parse_llm_clusters(raw_result=raw_result, window=window)
                candidates.extend(llm_candidates)
                filtered_candidates.extend(llm_filtered)

        self._emit_progress(
            "candidates_built",
            {
                "video_id": video_id,
                "candidate_count": len(candidates),
                "filtered_candidate_count": len(filtered_candidates),
                "llm_call_count": len(self.last_llm_calls),
            },
        )

        final_candidates = _select_final_candidates(
            candidates,
            max_cues_per_episode=self.max_cues_per_episode,
            min_gap_sec=self.min_cue_gap_sec,
        )
        cues = [
            _candidate_to_cue(
                video_id=video_id,
                candidate=candidate,
                index=index,
                duration_sec=self.duration_sec,
            )
            for index, candidate in enumerate(final_candidates, start=1)
        ]
        debug_cues = [
            {
                "cueId": cues[index]["cueId"],
                "windowId": str(candidate["windowId"]),
                "intentType": str(candidate["intentType"]),
                "sourceCommentIds": list(candidate["sourceCommentIds"]),
                "score": _round_time(float(candidate.get("score", 0.0))),
                "confidence": _round_time(float(candidate.get("confidence", 0.0))),
                "reason": str(candidate.get("reason") or ""),
            }
            for index, candidate in enumerate(final_candidates)
        ]
        result = {
            "videoId": video_id,
            "seriesId": series_id,
            "episodeId": episode_id,
            "createdAt": now_iso(),
            "cues": cues,
            "debug": {
                "sourceDanmakuCount": len(danmaku_items),
                "cleanDanmakuCount": len(normalized_items),
                "candidateWindowCount": len(windows),
                "rawCandidateCount": len(candidates),
                "filteredCandidateCount": len(filtered_candidates),
                "selectedCueCount": len(cues),
                "llmCallCount": len(self.last_llm_calls),
                "intentCounts": dict(Counter(str(candidate["intentType"]) for candidate in final_candidates)),
                "windows": [
                    {
                        "windowId": window.window_id,
                        "startTime": window.start_time,
                        "endTime": window.end_time,
                        "score": window.score,
                        "danmakuCount": len(window.items),
                        "uniqueTextCount": len({item.text for item in window.items}),
                        "repeatTextCount": max(Counter(item.text for item in window.items).values(), default=0),
                        "topComments": _top_window_comments(window, limit=8),
                    }
                    for window in windows
                ],
                "cues": debug_cues,
                "filteredCandidates": filtered_candidates,
                "llmCalls": self.last_llm_calls,
            },
        }
        self._emit_progress(
            "completed",
            {
                "video_id": video_id,
                "selected_cue_count": len(cues),
            },
        )
        return result


def generate_inner_voice_danmaku(
    *,
    video_id: str,
    series_id: str,
    episode_id: str,
    danmaku_items: list[dict[str, Any]],
    llm_client: LlmClientProtocol | None = None,
    enable_llm_semantic: bool = False,
    window_sec: float = 8.0,
    step_sec: float = 2.0,
    min_window_danmaku_count: int = 4,
    min_unique_text_count: int = 2,
    min_window_score: float = 6.0,
    max_cues_per_episode: int = 8,
    duration_sec: float = 5.0,
    min_cue_gap_sec: float = 12.0,
    llm_max_tokens: int = 1200,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    pipeline = InnerVoiceDanmakuPipeline(
        llm_client=llm_client,
        enable_llm_semantic=enable_llm_semantic,
        window_sec=window_sec,
        step_sec=step_sec,
        min_window_danmaku_count=min_window_danmaku_count,
        min_unique_text_count=min_unique_text_count,
        min_window_score=min_window_score,
        max_cues_per_episode=max_cues_per_episode,
        duration_sec=duration_sec,
        min_cue_gap_sec=min_cue_gap_sec,
        llm_max_tokens=llm_max_tokens,
        progress_callback=progress_callback,
    )
    return pipeline.run(
        video_id=video_id,
        series_id=series_id,
        episode_id=episode_id,
        danmaku_items=danmaku_items,
    )

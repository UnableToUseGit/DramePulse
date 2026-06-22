from __future__ import annotations

import json
import re
from typing import Any

from ..config import get_settings
from ..repositories.interactions import list_interaction_plans
from ..repositories.new_assets import list_video_interaction_items
from ..schemas import WatchAssistantRequest
from ..story_qa import service as story_qa_service


CONTROL_TOOLS = {"seek", "seek_relative", "next_episode", "pause", "resume"}
STORY_QA_KEYWORDS = ("谁", "什么", "为什么", "怎么", "关系", "刚才", "剧情", "发生", "解释", "他", "她")


def act(payload: WatchAssistantRequest) -> dict[str, Any]:
    rule_intent = _parse_with_rules(payload.message)
    if _has_control_tool(rule_intent):
        intent = rule_intent
    else:
        intent = _parse_with_llm(payload) or rule_intent
    return _execute_intent(payload, intent)


def _has_control_tool(intent: dict[str, Any]) -> bool:
    return any(str(tool.get("name") or "") in CONTROL_TOOLS for tool in intent.get("tools", []) if isinstance(tool, dict))


def _parse_with_llm(payload: WatchAssistantRequest) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_api_base)
        response = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是短剧播放器观看助手的意图路由器。只输出 JSON。"
                        "schema: {\"tools\":[{\"name\":\"story_qa|seek|seek_relative|next_episode|pause|resume|noop\","
                        "\"arguments\":{}}],\"reply\":\"短中文提示\"}。"
                        "播放器控制只返回工具，不要假装已经执行。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": payload.message,
                            "series_id": payload.series_id,
                            "video_id": payload.video_id,
                            "current_episode": payload.current_episode,
                            "current_time": payload.current_time,
                            "duration": payload.duration,
                            "available_tools": payload.available_tools,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        parsed = json.loads(content)
    except Exception:
        return None

    tools = parsed.get("tools")
    if not isinstance(tools, list):
        return None
    safe_tools = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "")
        if name not in {"story_qa", "seek", "seek_relative", "next_episode", "pause", "resume", "noop"}:
            continue
        arguments = tool.get("arguments")
        safe_arguments = arguments if isinstance(arguments, dict) else {}
        if name == "seek":
            safe_arguments = _normalize_seek_arguments(payload.message, safe_arguments)
        safe_tools.append({"name": name, "arguments": safe_arguments})
    if not safe_tools:
        return None
    reply = parsed.get("reply")
    return {"tools": safe_tools, "reply": reply if isinstance(reply, str) else ""}


def _parse_with_rules(message: str) -> dict[str, Any]:
    text = message.strip()
    tools: list[dict[str, Any]] = []

    if _mentions_highlight_target(text):
        tools.append({"name": "seek", "arguments": {"target": "highlight"}})

    if re.search(r"(下一集|下.?一[集话]|next)", text, re.IGNORECASE):
        tools.append({"name": "next_episode", "arguments": {}})
    if re.search(r"(暂停|停一下|pause)", text, re.IGNORECASE):
        tools.append({"name": "pause", "arguments": {}})
    if re.search(r"(继续|播放|resume|play)", text, re.IGNORECASE) and not re.search(r"(下一集|下.?一[集话])", text):
        tools.append({"name": "resume", "arguments": {}})

    absolute = _parse_absolute_time(text)
    if absolute is not None:
        tools.append({"name": "seek", "arguments": {"target_time": absolute}})
    elif re.search(r"(高光|精彩|爽点|名场面)", text):
        tools.append({"name": "seek", "arguments": {"target": "highlight"}})
    else:
        relative = _parse_relative_seek(text)
        if relative is not None:
            tools.append({"name": "seek_relative", "arguments": {"seconds": relative}})

    asks_story = any(keyword in text for keyword in STORY_QA_KEYWORDS) or text.endswith(("?", "？"))
    if asks_story:
        tools.insert(0, {"name": "story_qa", "arguments": {"question": text}})

    if not tools:
        tools.append({"name": "story_qa", "arguments": {"question": text}})
    return {"tools": _dedupe_tools(tools), "reply": ""}


def _dedupe_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for tool in tools:
        name = str(tool.get("name") or "")
        arguments = tool.get("arguments") if isinstance(tool.get("arguments"), dict) else {}
        key = (name, json.dumps(arguments, ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tool)
    return deduped


def _normalize_seek_arguments(message: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if isinstance(arguments.get("target_time"), (int, float)):
        return arguments
    target = str(arguments.get("target") or "").lower()
    if target in {"highlight", "highlight_point"}:
        return {**arguments, "target": "highlight"}
    if target in {"高光", "高光点", "精彩", "爽点", "名场面"} or _mentions_highlight_target(message):
        return {**arguments, "target": "highlight"}
    if target in {"高光", "精彩", "爽点", "名场面"} or re.search(r"(高光|精彩|爽点|名场面)", message):
        return {**arguments, "target": "highlight"}
    return arguments


def _mentions_highlight_target(text: str) -> bool:
    has_highlight_word = re.search(r"(楂樺厜|绮惧僵|鐖界偣|鍚嶅満闈?|高光|高光点|精彩|爽点|名场面)", text)
    has_seek_word = re.search(r"(璺冲埌|蹇繘|跳|跳到|切|切到|到|下一个|下个|下一处|下一段|next)", text, re.IGNORECASE)
    return bool(has_highlight_word and has_seek_word)


def _parse_relative_seek(text: str) -> float | None:
    match = re.search(r"(快进|往后|后退|退回|倒回|往前|forward|back)\s*(\d+(?:\.\d+)?)?\s*(秒|s|分钟|分)?", text, re.IGNORECASE)
    if not match:
        return None
    verb = match.group(1)
    amount = float(match.group(2) or 10)
    unit = match.group(3) or "秒"
    seconds = amount * 60 if unit in {"分钟", "分"} else amount
    if verb in {"后退", "退回", "倒回", "往前", "back"}:
        return -seconds
    return seconds


def _parse_absolute_time(text: str) -> float | None:
    minute_second = re.search(r"(\d+)\s*分\s*(\d+)\s*秒?", text)
    if minute_second:
        return float(int(minute_second.group(1)) * 60 + int(minute_second.group(2)))
    minute_only = re.search(r"(\d+)\s*分钟", text)
    if minute_only:
        return float(int(minute_only.group(1)) * 60)
    second_only = re.search(r"(?:跳到|到|seek)\s*(\d+(?:\.\d+)?)\s*(?:秒|s)?", text, re.IGNORECASE)
    if second_only:
        return float(second_only.group(1))
    return None


def _execute_intent(payload: WatchAssistantRequest, intent: dict[str, Any]) -> dict[str, Any]:
    reply_parts: list[str] = []
    actions: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for tool in intent.get("tools", []):
        name = str(tool.get("name") or "noop")
        arguments = tool.get("arguments") if isinstance(tool.get("arguments"), dict) else {}
        if name == "story_qa":
            result = _run_story_qa(payload, arguments)
            tool_calls.append(result["tool_call"])
            if result["reply"]:
                reply_parts.append(result["reply"])
                actions.append({"type": "answer", "reason": result["reply"]})
            sources.extend(result["sources"])
        elif name == "seek_relative":
            seconds = _float_arg(arguments.get("seconds"), 10)
            target_time = _clamp_time(payload.current_time + seconds, payload.duration)
            actions.append({"type": "seek", "target_time": target_time, "relative_seconds": seconds, "reason": "按助手指令调整播放进度"})
            tool_calls.append({"tool": name, "arguments": {"seconds": seconds}, "status": "ok", "result": {"target_time": target_time}})
            reply_parts.append(_seek_reply(target_time))
        elif name == "seek":
            arguments = _normalize_seek_arguments(payload.message, arguments)
            target_time = _resolve_seek_target(payload, arguments)
            if target_time is None:
                actions.append({"type": "noop", "reason": "当前视频没有可跳转的高光点"})
                tool_calls.append({"tool": name, "arguments": arguments, "status": "error", "result": {}, "error": "highlight target not found"})
                reply_parts.append("当前视频还没有可跳转的高光点。")
            else:
                target_time = _clamp_time(target_time, payload.duration)
                actions.append({"type": "seek", "target_time": target_time, "reason": "按助手指令跳转"})
                tool_calls.append({"tool": name, "arguments": arguments, "status": "ok", "result": {"target_time": target_time}})
                reply_parts.append(_seek_reply(target_time))
        elif name in {"next_episode", "pause", "resume"}:
            actions.append({"type": name, "reason": "按助手指令控制播放器"})
            tool_calls.append({"tool": name, "arguments": arguments, "status": "ok", "result": {}})
            reply_parts.append({"next_episode": "为你切到下一集。", "pause": "已准备暂停播放。", "resume": "已准备继续播放。"}[name])
        else:
            actions.append({"type": "noop", "reason": "未识别到可执行指令"})
            tool_calls.append({"tool": "noop", "arguments": arguments, "status": "ok", "result": {}})

    explicit_reply = intent.get("reply")
    reply = " ".join(part for part in reply_parts if part).strip() or (explicit_reply if isinstance(explicit_reply, str) else "")
    if not reply:
        reply = "我可以帮你问剧情、快进、暂停或切到下一集。"
    return {"reply": reply, "actions": actions, "tool_calls": tool_calls, "sources": sources}


def _run_story_qa(payload: WatchAssistantRequest, arguments: dict[str, Any]) -> dict[str, Any]:
    question = str(arguments.get("question") or payload.message).strip()
    try:
        answer = story_qa_service.ask(question, payload.series_id, payload.current_episode, payload.current_time)
        reply = str(answer.get("answer") or "").strip()
        sources = answer.get("sources") if isinstance(answer.get("sources"), list) else []
        return {
            "reply": reply,
            "sources": sources,
            "tool_call": {"tool": "story_qa", "arguments": {"question": question}, "status": "ok", "result": {"answer": reply}},
        }
    except Exception as exc:
        message = f"剧情资料暂时不可用：{exc}"
        return {
            "reply": message,
            "sources": [],
            "tool_call": {"tool": "story_qa", "arguments": {"question": question}, "status": "error", "result": {}, "error": str(exc)},
        }


def _resolve_seek_target(payload: WatchAssistantRequest, arguments: dict[str, Any]) -> float | None:
    target_time = arguments.get("target_time")
    if isinstance(target_time, (int, float)):
        return float(target_time)
    target = str(arguments.get("target") or "").lower()
    if target not in {"highlight", "highlight_point"} and str(arguments.get("target") or "") not in {"高光", "精彩", "爽点", "名场面"}:
        return None
    plans = list_interaction_plans(payload.video_id)
    future_plans = [plan for plan in plans if float(plan.get("trigger_time") or 0) >= payload.current_time]
    selected = future_plans[0] if future_plans else (plans[0] if plans else None)
    if selected:
        return float(selected.get("trigger_time") or 0)

    items = list_video_interaction_items(payload.video_id)
    future_items = [item for item in items if float(item.get("trigger_time") or 0) >= payload.current_time]
    selected_item = future_items[0] if future_items else (items[0] if items else None)
    if not selected_item:
        return None
    return float(selected_item.get("trigger_time") or 0)


def _float_arg(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else fallback
    except Exception:
        return fallback


def _clamp_time(value: float, duration: float) -> float:
    upper = duration if duration > 0 else value
    return max(0.0, min(float(value), float(upper)))


def _seek_reply(target_time: float) -> str:
    return f"已准备跳到 {int(target_time // 60)}:{int(target_time % 60):02d}。"

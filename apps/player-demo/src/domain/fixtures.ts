import danmakuPayload from "../fixtures/danmaku.json";
import interactionPlanPayload from "../fixtures/interaction-plan-generation.json";
import type { DanmakuItem, InteractionFeedback, InteractionPlan, PlayerFixtures } from "./types";

type RawDanmakuPayload = {
  danmaku?: unknown;
};

type RawInteractionPayload = {
  video_id?: unknown;
  interaction_plans?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function normalizeDanmakuItems(payload: RawDanmakuPayload): DanmakuItem[] {
  const rawItems = Array.isArray(payload.danmaku) ? payload.danmaku : [];
  return rawItems
    .filter(isRecord)
    .map((item) => ({
      danmaku_id: typeof item.danmaku_id === "string" ? item.danmaku_id : undefined,
      time_sec: toNumber(item.time_sec),
      text: toStringValue(item.text).trim(),
      digg_count: typeof item.digg_count === "number" ? item.digg_count : undefined,
      score: typeof item.score === "number" ? item.score : undefined
    }))
    .filter((item) => item.text.length > 0)
    .sort((a, b) => a.time_sec - b.time_sec);
}

function normalizeFeedback(value: unknown): InteractionFeedback {
  if (!isRecord(value)) {
    return {
      type: "poll_result",
      show_ratio: true,
      show_resonance_text: true,
      resonance_text_template: "你和 {ratio}% 的观众一样选择了「{option}」"
    };
  }

  const type = toStringValue(value.type, "poll_result");
  return {
    type:
      type === "resonance_text" || type === "danmaku_burst" || type === "none" || type === "poll_result"
        ? type
        : "poll_result",
    show_ratio: typeof value.show_ratio === "boolean" ? value.show_ratio : true,
    show_resonance_text: typeof value.show_resonance_text === "boolean" ? value.show_resonance_text : true,
    resonance_text_template: toStringValue(
      value.resonance_text_template,
      "你和 {ratio}% 的观众一样选择了「{option}」"
    )
  };
}

function normalizeInteractionPlans(payload: RawInteractionPayload): InteractionPlan[] {
  const rawPlans = Array.isArray(payload.interaction_plans) ? payload.interaction_plans : [];
  return rawPlans
    .filter(isRecord)
    .filter((plan) => plan.interaction_type === "danmaku_poll" && plan.status !== "disabled")
    .map((plan) => ({
      interaction_id: toStringValue(plan.interaction_id),
      highlight_id: toStringValue(plan.highlight_id),
      video_id: toStringValue(plan.video_id),
      trigger_time: toNumber(plan.trigger_time),
      expire_time: toNumber(plan.expire_time),
      interaction_type: "danmaku_poll" as const,
      question: toStringValue(plan.question),
      options: Array.isArray(plan.options)
        ? plan.options.filter(isRecord).map((option) => ({
            option_id: toStringValue(option.option_id),
            text: toStringValue(option.text),
            danmaku_text: toStringValue(option.danmaku_text),
            rank: typeof option.rank === "number" ? option.rank : undefined,
            base_score: typeof option.base_score === "number" ? option.base_score : undefined
          }))
        : [],
      feedback: normalizeFeedback(plan.feedback),
      display_position: toStringValue(plan.display_position, "subtitle_safe_area"),
      status: toStringValue(plan.status, "active") as InteractionPlan["status"]
    }))
    .filter((plan) => plan.interaction_id && plan.highlight_id && plan.question && plan.options.length >= 2)
    .sort((a, b) => a.trigger_time - b.trigger_time);
}

export function getDemoFixtures(): PlayerFixtures {
  const interactionPayload = interactionPlanPayload as RawInteractionPayload;
  return {
    videoId: toStringValue(interactionPayload.video_id, "case1_ep01"),
    danmaku: normalizeDanmakuItems(danmakuPayload as RawDanmakuPayload),
    interactionPlans: normalizeInteractionPlans(interactionPayload)
  };
}

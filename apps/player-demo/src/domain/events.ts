import type { InteractionEventType, InteractionPlan, InteractionStats, UserEvent } from "./types";

const DEMO_USER_ID = "u_demo_001";
const DEMO_DEVICE = "expo_go";

export function createInitialStats(): InteractionStats {
  return {
    exposure_count: 0,
    click_count: 0,
    feedback_shown_count: 0,
    dismiss_count: 0,
    option_click_count: {},
    option_click_rate: {}
  };
}

export function createUserEvent({
  eventType,
  plan,
  optionId,
  clientTime,
  nowSeconds = Math.floor(Date.now() / 1000)
}: {
  eventType: InteractionEventType;
  plan: InteractionPlan;
  optionId?: string;
  clientTime: number;
  nowSeconds?: number;
}): UserEvent {
  return {
    event_type: eventType,
    user_id: DEMO_USER_ID,
    video_id: plan.video_id,
    highlight_id: plan.highlight_id,
    interaction_id: plan.interaction_id,
    option_id: optionId,
    client_time: clientTime,
    timestamp: nowSeconds,
    extra: {
      interaction_type: plan.interaction_type,
      device: DEMO_DEVICE
    }
  };
}

function recomputeOptionRates(stats: InteractionStats): Record<string, number> {
  if (stats.click_count === 0) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(stats.option_click_count).map(([optionId, count]) => [optionId, count / stats.click_count])
  );
}

export function updateStats(currentStats: InteractionStats | undefined, event: UserEvent): InteractionStats {
  const stats = currentStats ?? createInitialStats();
  const nextStats: InteractionStats = {
    exposure_count: stats.exposure_count,
    click_count: stats.click_count,
    feedback_shown_count: stats.feedback_shown_count,
    dismiss_count: stats.dismiss_count,
    option_click_count: { ...stats.option_click_count },
    option_click_rate: { ...stats.option_click_rate }
  };

  if (event.event_type === "interaction_exposure") {
    nextStats.exposure_count += 1;
  }
  if (event.event_type === "option_click") {
    nextStats.click_count += 1;
    if (event.option_id) {
      nextStats.option_click_count[event.option_id] = (nextStats.option_click_count[event.option_id] ?? 0) + 1;
    }
  }
  if (event.event_type === "feedback_shown") {
    nextStats.feedback_shown_count += 1;
  }
  if (event.event_type === "interaction_dismiss") {
    nextStats.dismiss_count += 1;
  }

  nextStats.option_click_rate = recomputeOptionRates(nextStats);
  return nextStats;
}

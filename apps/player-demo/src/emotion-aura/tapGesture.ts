import type { EmotionEnergyLevel } from "./types";

export const TAP_SINGLE_DELAY_MS = 180;
export const TAP_SETTLE_DELAY_MS = 400;

export type TapGesturePhase = "idle" | "tap_pending" | "tapping" | "settled";

export type TapGestureAction = "none" | "toggle_playback" | "start_emotion" | "emotion_tap" | "settle_emotion";

export type TapGestureState = {
  phase: TapGesturePhase;
  tapCount: number;
  lastTapMs?: number;
  nextDeadlineMs?: number;
  action: TapGestureAction;
};

export type TapGestureEvent = { type: "tap"; nowMs: number } | { type: "time"; nowMs: number } | { type: "reset" };

export function createInitialTapGestureState(): TapGestureState {
  return {
    phase: "idle",
    tapCount: 0,
    action: "none"
  };
}

function withoutAction(state: TapGestureState): TapGestureState {
  return { ...state, action: "none" };
}

export function reduceTapGesture(state: TapGestureState, event: TapGestureEvent): TapGestureState {
  if (event.type === "reset") {
    return createInitialTapGestureState();
  }

  if (event.type === "tap") {
    if (state.phase === "tap_pending") {
      return {
        phase: "tapping",
        tapCount: 2,
        lastTapMs: event.nowMs,
        nextDeadlineMs: event.nowMs + TAP_SETTLE_DELAY_MS,
        action: "start_emotion"
      };
    }

    if (state.phase === "tapping") {
      return {
        phase: "tapping",
        tapCount: state.tapCount + 1,
        lastTapMs: event.nowMs,
        nextDeadlineMs: event.nowMs + TAP_SETTLE_DELAY_MS,
        action: "emotion_tap"
      };
    }

    return {
      phase: "tap_pending",
      tapCount: 1,
      lastTapMs: event.nowMs,
      nextDeadlineMs: event.nowMs + TAP_SINGLE_DELAY_MS,
      action: "none"
    };
  }

  if (state.phase === "tap_pending" && state.nextDeadlineMs !== undefined && event.nowMs >= state.nextDeadlineMs) {
    return {
      phase: "idle",
      tapCount: 0,
      action: "toggle_playback"
    };
  }

  if (state.phase === "tapping" && state.nextDeadlineMs !== undefined && event.nowMs >= state.nextDeadlineMs) {
    return {
      ...state,
      phase: "settled",
      action: "settle_emotion"
    };
  }

  return withoutAction(state);
}

export function getEmotionEnergyLevel(tapCount: number): EmotionEnergyLevel {
  if (tapCount >= 7) {
    return "high";
  }
  if (tapCount >= 3) {
    return "medium";
  }
  return "low";
}

export function canAutoDismissEmotionAura(state: TapGestureState) {
  return state.phase === "idle" && state.tapCount === 0;
}

export function isEmotionExpressionVisible(state: TapGestureState) {
  return state.phase === "tapping" || state.phase === "settled";
}

export type EmotionHapticFeedback = "selection";

export function getEmotionHapticFeedback(action: TapGestureAction): EmotionHapticFeedback | undefined {
  if (action === "start_emotion" || action === "emotion_tap") {
    return "selection";
  }
  return undefined;
}

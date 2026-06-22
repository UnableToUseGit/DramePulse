import {
  canAutoDismissEmotionAura,
  createInitialTapGestureState,
  getEmotionEnergyLevel,
  getEmotionHapticFeedback,
  isEmotionExpressionVisible,
  reduceTapGesture,
  TAP_SETTLE_DELAY_MS,
  TAP_SINGLE_DELAY_MS
} from "../tapGesture";

describe("emotion aura tap gesture reducer", () => {
  it("keeps a single tap pending until the pause delay elapses", () => {
    const state = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });

    expect(state.phase).toBe("tap_pending");
    expect(state.tapCount).toBe(1);
    expect(state.action).toBe("none");
    expect(state.nextDeadlineMs).toBe(1000 + TAP_SINGLE_DELAY_MS);
  });

  it("turns a pending single tap into a playback toggle after the delay", () => {
    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    const state = reduceTapGesture(pending, { type: "time", nowMs: 1000 + TAP_SINGLE_DELAY_MS });

    expect(state.phase).toBe("idle");
    expect(state.tapCount).toBe(0);
    expect(state.action).toBe("toggle_playback");
  });

  it("enters emotion tapping when a second tap arrives inside the pending window", () => {
    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    const state = reduceTapGesture(pending, { type: "tap", nowMs: 1120 });

    expect(state.phase).toBe("tapping");
    expect(state.tapCount).toBe(2);
    expect(state.action).toBe("start_emotion");
    expect(state.nextDeadlineMs).toBe(1120 + TAP_SETTLE_DELAY_MS);
  });

  it("keeps accumulating taps while emotion tapping is active", () => {
    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    const tapping = reduceTapGesture(pending, { type: "tap", nowMs: 1120 });
    const state = reduceTapGesture(tapping, { type: "tap", nowMs: 1300 });

    expect(state.phase).toBe("tapping");
    expect(state.tapCount).toBe(3);
    expect(state.action).toBe("emotion_tap");
    expect(state.nextDeadlineMs).toBe(1300 + TAP_SETTLE_DELAY_MS);
  });

  it("settles emotion tapping after the idle delay", () => {
    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    const tapping = reduceTapGesture(pending, { type: "tap", nowMs: 1120 });
    const state = reduceTapGesture(tapping, { type: "time", nowMs: 1120 + TAP_SETTLE_DELAY_MS });

    expect(state.phase).toBe("settled");
    expect(state.tapCount).toBe(2);
    expect(state.action).toBe("settle_emotion");
  });

  it("maps tap count to low, medium, and high energy", () => {
    expect(getEmotionEnergyLevel(1)).toBe("low");
    expect(getEmotionEnergyLevel(2)).toBe("low");
    expect(getEmotionEnergyLevel(3)).toBe("medium");
    expect(getEmotionEnergyLevel(6)).toBe("medium");
    expect(getEmotionEnergyLevel(7)).toBe("high");
  });

  it("resets pending gesture state", () => {
    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    const state = reduceTapGesture(pending, { type: "reset" });

    expect(state).toEqual(createInitialTapGestureState());
  });

  it("only auto dismisses before the user starts tapping", () => {
    expect(canAutoDismissEmotionAura(createInitialTapGestureState())).toBe(true);

    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    expect(canAutoDismissEmotionAura(pending)).toBe(false);

    const tapping = reduceTapGesture(pending, { type: "tap", nowMs: 1120 });
    expect(canAutoDismissEmotionAura(tapping)).toBe(false);

    const settled = reduceTapGesture(tapping, { type: "time", nowMs: 1120 + TAP_SETTLE_DELAY_MS });
    expect(canAutoDismissEmotionAura(settled)).toBe(false);
  });

  it("does not show emotion feedback for a pending single tap", () => {
    const pending = reduceTapGesture(createInitialTapGestureState(), { type: "tap", nowMs: 1000 });
    expect(isEmotionExpressionVisible(pending)).toBe(false);

    const tapping = reduceTapGesture(pending, { type: "tap", nowMs: 1120 });
    expect(isEmotionExpressionVisible(tapping)).toBe(true);

    const settled = reduceTapGesture(tapping, { type: "time", nowMs: 1120 + TAP_SETTLE_DELAY_MS });
    expect(isEmotionExpressionVisible(settled)).toBe(true);
  });

  it("only triggers haptic feedback for real emotion taps", () => {
    expect(getEmotionHapticFeedback("none")).toBeUndefined();
    expect(getEmotionHapticFeedback("toggle_playback")).toBeUndefined();
    expect(getEmotionHapticFeedback("settle_emotion")).toBeUndefined();
    expect(getEmotionHapticFeedback("start_emotion")).toBe("selection");
    expect(getEmotionHapticFeedback("emotion_tap")).toBe("selection");
  });
});

import {
  getInnerVoiceDragState,
  getInnerVoiceFlingVelocity,
  getInnerVoiceLaunchTarget,
  shouldClaimInnerVoiceDrag,
  shouldSendInnerVoiceDraft
} from "../gesture";

describe("inner voice danmaku gesture helpers", () => {
  it("sends when the draft is pushed straight upward", () => {
    expect(shouldSendInnerVoiceDraft({ dx: 4, dy: -42 })).toBe(true);
  });

  it("claims upward drag intent from the draft so feed swipes can be locked", () => {
    expect(shouldClaimInnerVoiceDrag({ dx: 3, dy: -8 })).toBe(true);
    expect(shouldClaimInnerVoiceDrag({ dx: 16, dy: -10 })).toBe(false);
  });

  it("sends when the draft is pushed diagonally up and right", () => {
    expect(shouldSendInnerVoiceDraft({ dx: 34, dy: -18 })).toBe(true);
  });

  it("does not send for taps, short drags, or downward movement", () => {
    expect(shouldSendInnerVoiceDraft({ dx: 0, dy: 0 })).toBe(false);
    expect(shouldSendInnerVoiceDraft({ dx: 8, dy: -12 })).toBe(false);
    expect(shouldSendInnerVoiceDraft({ dx: 32, dy: 8 })).toBe(false);
  });

  it("keeps the draft directly under the finger while dragging", () => {
    expect(getInnerVoiceDragState({ dx: 20, dy: -40 })).toEqual({
      translateX: 20,
      translateY: -40,
      progress: 1
    });
  });

  it("throws the draft farther when the upward fling is faster", () => {
    expect(getInnerVoiceLaunchTarget({ dx: 12, dy: -38, vy: -0.2 })).toEqual({
      translateX: 24,
      translateY: -198
    });
    expect(getInnerVoiceLaunchTarget({ dx: 12, dy: -38, vy: -1.6 })).toEqual({
      translateX: 24,
      translateY: -254
    });
  });

  it("converts release velocity into a strong upward fling", () => {
    expect(getInnerVoiceFlingVelocity({ vx: 0.2, vy: -0.2 })).toEqual({
      velocityX: 200,
      velocityY: -1050
    });
    expect(getInnerVoiceFlingVelocity({ vx: 2.4, vy: -1.6 })).toEqual({
      velocityX: 1400,
      velocityY: -2120
    });
  });
});

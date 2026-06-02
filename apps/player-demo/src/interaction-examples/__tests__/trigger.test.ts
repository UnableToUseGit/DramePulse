import { DEFAULT_INTERACTION_EXAMPLE } from "../examples";
import { getPresentationLabel, shouldResetExample, shouldShowExample } from "../trigger";

describe("interaction example trigger helpers", () => {
  it("maps presentation types to developer-facing labels", () => {
    expect(getPresentationLabel("none")).toBe("Off");
    expect(getPresentationLabel("poll_bar")).toBe("Poll Bar");
    expect(getPresentationLabel("danmaku_poll")).toBe("Danmaku Poll");
    expect(getPresentationLabel("emoji_hold")).toBe("Emoji Hold");
    expect(getPresentationLabel("emotion_aura")).toBe("Emotion Aura");
    expect(getPresentationLabel("inner_voice_danmaku")).toBe("Inner Voice");
    expect(getPresentationLabel("action_rail_resonance")).toBe("Rail Resonance");
  });

  it("shows the selected example immediately after playback starts", () => {
    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec - 0.1,
        isStarted: true,
        dismissed: false,
        presentationType: "poll_bar"
      })
    ).toBe(true);

    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec,
        isStarted: false,
        dismissed: false,
        presentationType: "poll_bar"
      })
    ).toBe(false);

    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec,
        isStarted: true,
        dismissed: false,
        presentationType: "poll_bar"
      })
    ).toBe(true);
  });

  it("does not show examples when disabled or dismissed", () => {
    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec + 1,
        isStarted: true,
        dismissed: false,
        presentationType: "none"
      })
    ).toBe(false);

    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec + 1,
        isStarted: true,
        dismissed: true,
        presentationType: "emotion_aura"
      })
    ).toBe(false);
  });

  it("resets the example when seeking back before the trigger", () => {
    expect(
      shouldResetExample({
        previousTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec + 1,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec - 1,
        triggerTimeSec: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec
      })
    ).toBe(true);

    expect(
      shouldResetExample({
        previousTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec + 2,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec + 3,
        triggerTimeSec: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec
      })
    ).toBe(false);
  });
});

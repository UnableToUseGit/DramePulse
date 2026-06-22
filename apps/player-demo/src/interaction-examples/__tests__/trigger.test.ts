import { DEFAULT_INTERACTION_EXAMPLE } from "../examples";
import {
  getPresentationLabel,
  isActionRailResonancePresentation,
  shouldResetExample,
  shouldShowExample
} from "../trigger";

describe("interaction example trigger helpers", () => {
  it("maps presentation types to developer-facing labels", () => {
    expect(getPresentationLabel("none")).toBe("Off");
    expect(getPresentationLabel("danmaku_poll")).toBe("Danmaku Poll");
    expect(getPresentationLabel("inner_voice_danmaku")).toBe("Inner Voice");
    expect(getPresentationLabel("action_rail_thrill")).toBe("Rail 爽点");
    expect(getPresentationLabel("action_rail_candy")).toBe("Rail 撒糖");
    expect(getPresentationLabel("action_rail_laugh")).toBe("Rail 大笑");
    expect(getPresentationLabel("action_rail_tear")).toBe("Rail 泪目");
  });

  it("identifies action rail resonance debug presentations", () => {
    expect(isActionRailResonancePresentation("action_rail_thrill")).toBe(true);
    expect(isActionRailResonancePresentation("action_rail_candy")).toBe(true);
    expect(isActionRailResonancePresentation("action_rail_laugh")).toBe(true);
    expect(isActionRailResonancePresentation("action_rail_tear")).toBe(true);
    expect(isActionRailResonancePresentation("danmaku_poll")).toBe(false);
  });

  it("shows the selected example immediately after playback starts", () => {
    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec - 0.1,
        isStarted: true,
        dismissed: false,
        presentationType: "danmaku_poll"
      })
    ).toBe(true);

    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec,
        isStarted: false,
        dismissed: false,
        presentationType: "danmaku_poll"
      })
    ).toBe(false);

    expect(
      shouldShowExample({
        example: DEFAULT_INTERACTION_EXAMPLE,
        currentTime: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec,
        isStarted: true,
        dismissed: false,
        presentationType: "danmaku_poll"
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
        presentationType: "action_rail_candy"
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

import {
  getActiveActionRailResonanceCue,
  getVisibleActionRailResonanceCue,
  shouldResetActionRailResonanceCue
} from "../scheduler";
import type { ActionRailResonanceCue } from "../types";

const cues: ActionRailResonanceCue[] = [
  {
    cueId: "resonance_1",
    videoId: "case1_ep01",
    highlightId: "h_1",
    triggerTime: 8,
    durationSec: 5,
    emotionType: "爽点",
    label: "爽到了",
    icon: "flame",
    baseCount: 82000,
    feedbackText: "你也爽到了"
  }
];

describe("action rail resonance scheduler", () => {
  it("returns the active cue inside its display window", () => {
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 8, completedCueIds: new Set() })?.cueId).toBe(
      "resonance_1"
    );
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 12.9, completedCueIds: new Set() })?.cueId).toBe(
      "resonance_1"
    );
  });

  it("does not return cues before trigger, after expiry, or after completion", () => {
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 7.9, completedCueIds: new Set() })).toBeUndefined();
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 13.1, completedCueIds: new Set() })).toBeUndefined();
    expect(
      getActiveActionRailResonanceCue({ cues, currentTime: 9, completedCueIds: new Set(["resonance_1"]) })
    ).toBeUndefined();
  });

  it("resets completed cue memory when seeking before the earliest cue", () => {
    expect(shouldResetActionRailResonanceCue({ previousTime: 20, currentTime: 2, firstTriggerTime: 8 })).toBe(true);
    expect(shouldResetActionRailResonanceCue({ previousTime: 20, currentTime: 10, firstTriggerTime: 8 })).toBe(false);
  });

  it("does not keep a participating cue visible after the button has been tapped", () => {
    expect(
      getVisibleActionRailResonanceCue({
        activeCue: undefined,
        participatingCue: cues[0]
      })?.cueId
    ).toBeUndefined();
    expect(
      getVisibleActionRailResonanceCue({
        activeCue: cues[0],
        participatingCue: cues[0]
      })?.cueId
    ).toBe("resonance_1");
  });
});

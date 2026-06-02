import {
  findActiveEmotionAuraCue,
  getSettlingEmotionAuraCue,
  getVisibleEmotionAuraCue,
  shouldResetEmotionAuraCue,
  shouldTimeoutEmotionAuraCue
} from "../scheduler";
import type { EmotionAuraCue } from "../types";

const cues: EmotionAuraCue[] = [
  {
    cueId: "aura_1",
    videoId: "demo_ep01",
    highlightId: "h_1",
    triggerTime: 8,
    durationSec: 5,
    emotionType: "爽点",
    label: "爽到了",
    resonanceText: "你和 2.4 万人一起爽到了"
  },
  {
    cueId: "aura_2",
    videoId: "demo_ep01",
    highlightId: "h_2",
    triggerTime: 16,
    durationSec: 5,
    emotionType: "甜点",
    label: "磕到了",
    resonanceText: "你和 3.1 万人一起磕到了"
  }
];

describe("emotion aura scheduler", () => {
  it("returns no cue before the trigger time", () => {
    expect(findActiveEmotionAuraCue({ cues, currentTime: 7.9, completedCueIds: new Set() })).toBeUndefined();
  });

  it("returns the first uncompleted cue inside its trigger window", () => {
    expect(findActiveEmotionAuraCue({ cues, currentTime: 8, completedCueIds: new Set() })?.cueId).toBe("aura_1");
    expect(findActiveEmotionAuraCue({ cues, currentTime: 12.9, completedCueIds: new Set() })?.cueId).toBe("aura_1");
  });

  it("skips completed cues", () => {
    expect(findActiveEmotionAuraCue({ cues, currentTime: 9, completedCueIds: new Set(["aura_1"]) })).toBeUndefined();
  });

  it("keeps an engaged cue visible after its trigger window", () => {
    expect(
      getVisibleEmotionAuraCue({
        activeCue: undefined,
        engagedCue: cues[0],
        settledCue: undefined
      })?.cueId
    ).toBe("aura_1");
  });

  it("prioritizes settled feedback over active and engaged cues", () => {
    expect(
      getVisibleEmotionAuraCue({
        activeCue: cues[0],
        engagedCue: cues[0],
        settledCue: cues[1]
      })?.cueId
    ).toBe("aura_2");
  });

  it("settles the engaged cue even after the active time window has ended", () => {
    expect(getSettlingEmotionAuraCue({ activeCue: undefined, engagedCue: cues[0] })?.cueId).toBe("aura_1");
  });

  it("falls back to active cue when settling starts before the time window ends", () => {
    expect(getSettlingEmotionAuraCue({ activeCue: cues[0], engagedCue: undefined })?.cueId).toBe("aura_1");
  });

  it("times out cues after their duration", () => {
    expect(shouldTimeoutEmotionAuraCue({ cue: cues[0], currentTime: 12.9 })).toBe(false);
    expect(shouldTimeoutEmotionAuraCue({ cue: cues[0], currentTime: 13.1 })).toBe(true);
  });

  it("resets a cue after seeking back before its trigger", () => {
    expect(shouldResetEmotionAuraCue({ cue: cues[0], previousTime: 10, currentTime: 7.5 })).toBe(true);
    expect(shouldResetEmotionAuraCue({ cue: cues[0], previousTime: 10, currentTime: 9 })).toBe(false);
  });
});

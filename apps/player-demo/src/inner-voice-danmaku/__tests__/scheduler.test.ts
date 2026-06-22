import { getActiveInnerVoiceCue, getVisibleInnerVoiceCue, shouldResetInnerVoiceCue } from "../scheduler";
import type { InnerVoiceDanmakuCue } from "../types";

const cues: InnerVoiceDanmakuCue[] = [
  {
    cueId: "voice-1",
    videoId: "case1_ep01",
    highlightId: "h1",
    triggerTime: 8,
    durationSec: 4,
    text: "她终于怼回去了",
    danmakuTrack: 1
  },
  {
    cueId: "voice-2",
    videoId: "case1_ep01",
    highlightId: "h2",
    triggerTime: 18,
    durationSec: 4,
    text: "这俩绝对有事",
    danmakuTrack: 2
  }
];

describe("inner voice danmaku scheduler", () => {
  it("returns the cue while playback is inside its display window", () => {
    expect(getActiveInnerVoiceCue({ cues, currentTime: 8, completedCueIds: new Set() })?.cueId).toBe("voice-1");
    expect(getActiveInnerVoiceCue({ cues, currentTime: 11.9, completedCueIds: new Set() })?.cueId).toBe("voice-1");
  });

  it("does not return cues before trigger, after expiry, or after completion", () => {
    expect(getActiveInnerVoiceCue({ cues, currentTime: 7.9, completedCueIds: new Set() })).toBeUndefined();
    expect(getActiveInnerVoiceCue({ cues, currentTime: 12.1, completedCueIds: new Set() })).toBeUndefined();
    expect(getActiveInnerVoiceCue({ cues, currentTime: 8.5, completedCueIds: new Set(["voice-1"]) })).toBeUndefined();
  });

  it("resets completed cue memory when seeking before the earliest cue", () => {
    expect(shouldResetInnerVoiceCue({ previousTime: 20, currentTime: 2, firstTriggerTime: 8 })).toBe(true);
    expect(shouldResetInnerVoiceCue({ previousTime: 20, currentTime: 10, firstTriggerTime: 8 })).toBe(false);
  });

  it("keeps the launching cue visible after send starts", () => {
    expect(getVisibleInnerVoiceCue({ activeCue: undefined, launchingCue: cues[0] })?.cueId).toBe("voice-1");
    expect(getVisibleInnerVoiceCue({ activeCue: cues[1], launchingCue: cues[0] })?.cueId).toBe("voice-1");
  });
});

import {
  getExpiredInteractionCueIds,
  getSeekSkippedInteractionCueIds,
  toInteractionDebugMarkers,
  toActionRailResonanceCues,
  toInnerVoiceDanmakuCues
} from "../interactionAssetCues";
import type { InteractionAsset } from "../playerDataApi";

const assets: InteractionAsset[] = [
  {
    interactionId: "emotion-1",
    videoId: "v1",
    interactionMode: "emotional_button",
    triggerTime: 82.2,
    expireTime: 90.2,
    durationSec: 8,
    content: { expression_type: "笑点" },
    sourceAssetId: "h1",
    status: "active"
  },
  {
    interactionId: "voice-1",
    videoId: "v1",
    interactionMode: "inner_voice_danmaku",
    triggerTime: 56.807,
    expireTime: 64.807,
    durationSec: 8,
    content: { text: "这老板真是好人啊" },
    sourceAssetId: "h2",
    status: "active"
  }
];

describe("interactionAssetCues", () => {
  it("maps emotional_button assets to action rail resonance cues", () => {
    expect(toActionRailResonanceCues(assets)).toEqual([
      {
        cueId: "emotion-1",
        videoId: "v1",
        highlightId: "h1",
        triggerTime: 82.2,
        durationSec: 8,
        emotionType: "笑点",
        label: "笑到了",
        icon: "happy",
        baseCount: 0,
        feedbackText: "笑到了"
      }
    ]);
  });

  it("maps inner_voice_danmaku assets to inner voice cues", () => {
    expect(toInnerVoiceDanmakuCues(assets)).toEqual([
      {
        cueId: "voice-1",
        videoId: "v1",
        highlightId: "h2",
        triggerTime: 56.807,
        durationSec: 8,
        text: "这老板真是好人啊"
      }
    ]);
  });

  it("uses duration_sec when expire_time is missing", () => {
    const [cue] = toInnerVoiceDanmakuCues([
      {
        interactionId: "voice-2",
        videoId: "v1",
        interactionMode: "inner_voice_danmaku",
        triggerTime: 10,
        durationSec: 6,
        content: { text: "应该回家过年" },
        status: "active"
      }
    ]);

    expect(cue?.durationSec).toBe(6);
  });

  it("returns uncompleted cue ids whose display windows have expired", () => {
    const expired = getExpiredInteractionCueIds({
      cues: [...toActionRailResonanceCues(assets), ...toInnerVoiceDanmakuCues(assets)],
      currentTime: 91,
      completedCueIds: new Set(["voice-1"])
    });

    expect(expired).toEqual(["emotion-1"]);
  });

  it("returns uncompleted cue ids when a user seek lands inside their display windows", () => {
    const skipped = getSeekSkippedInteractionCueIds({
      cues: [...toActionRailResonanceCues(assets), ...toInnerVoiceDanmakuCues(assets)],
      seekTime: 58,
      completedCueIds: new Set(["emotion-1"])
    });

    expect(skipped).toEqual(["voice-1"]);
  });

  it("maps interaction assets to debug timeline markers", () => {
    expect(toInteractionDebugMarkers(assets)).toEqual([
      {
        markerId: "voice-1",
        time: 56.807,
        mode: "inner_voice_danmaku"
      },
      {
        markerId: "emotion-1",
        time: 82.2,
        mode: "emotional_button"
      }
    ]);
  });
});

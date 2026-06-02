import { createSentInnerVoiceDanmaku, toDanmakuItems } from "../sentDanmaku";

describe("inner voice sent danmaku adapter", () => {
  it("creates a formal danmaku item at the send time", () => {
    const sent = createSentInnerVoiceDanmaku({
      cueId: "voice-1",
      text: "她终于怼回去了",
      currentTime: 12.3,
      nowMs: 1000
    });

    expect(toDanmakuItems([sent])).toEqual([
      {
        danmaku_id: "voice-1-1000",
        time_sec: 12.3,
        text: "她终于怼回去了"
      }
    ]);
  });
});

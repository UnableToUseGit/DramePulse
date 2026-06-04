import {
  formatHomeFeedPlaybackEvent,
  formatHomeFeedPlaybackLatency,
  formatHomeFeedPlaybackPage
} from "../homeFeedPlaybackDebug";

describe("homeFeedPlaybackDebug", () => {
  it("formats missing latency without inventing a value", () => {
    expect(formatHomeFeedPlaybackLatency(undefined)).toBe("—");
    expect(formatHomeFeedPlaybackLatency(84)).toBe("84 ms");
  });

  it("formats a compact page status line", () => {
    expect(
      formatHomeFeedPlaybackPage({
        videoId: "case1_ep02",
        pageIndex: 1,
        isMounted: true,
        isPreloaded: true,
        hasPlaybackOwnership: false,
        playerStatus: "readyToPlay",
        isPlaying: false,
        isMuted: true
      })
    ).toBe("01 case1_ep02 · ready · paused · muted · preload");
  });

  it("does not present unknown native player state as a fact", () => {
    expect(
      formatHomeFeedPlaybackPage({
        videoId: "case1_ep03",
        pageIndex: 2,
        isMounted: true,
        isPreloaded: false,
        hasPlaybackOwnership: false
      })
    ).toBe("02 case1_ep03 · no-player · play? · mute? · idle");
  });

  it("formats recent events with elapsed time and key state", () => {
    expect(
      formatHomeFeedPlaybackEvent({
        sequence: 12,
        timestampMs: 1084,
        elapsedMs: 84,
        eventType: "playing_change",
        videoId: "case1_ep02",
        pageIndex: 1,
        details: { isPlaying: true }
      })
    ).toBe("+0084 #12 playing_change case1_ep02 isPlaying=true");
  });
});

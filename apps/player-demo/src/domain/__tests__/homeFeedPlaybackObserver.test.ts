import { createHomeFeedPlaybackObserver } from "../homeFeedPlaybackObserver";

describe("homeFeedPlaybackObserver", () => {
  function createClock(start = 1000) {
    let now = start;
    return {
      advance(ms: number) {
        now += ms;
      },
      now: () => now
    };
  }

  it("keeps only the most recent events", () => {
    const observer = createHomeFeedPlaybackObserver({
      maxEvents: 2,
      log: () => {}
    });

    observer.record({ eventType: "feed_scroll_begin" });
    observer.record({ eventType: "feed_scroll_end" });
    observer.record({ eventType: "feed_scroll_begin" });

    expect(observer.getSnapshot().events.map((event) => event.sequence)).toEqual([2, 3]);
  });

  it("deduplicates consecutive identical state events but keeps command events", () => {
    const observer = createHomeFeedPlaybackObserver({ log: () => {} });
    const playingEvent = {
      eventType: "playing_change" as const,
      videoId: "ep01",
      pageIndex: 0,
      details: { isPlaying: false }
    };

    observer.record(playingEvent);
    observer.record(playingEvent);
    observer.record({ eventType: "pause_command", videoId: "ep01", pageIndex: 0 });
    observer.record({ eventType: "pause_command", videoId: "ep01", pageIndex: 0 });

    expect(observer.getSnapshot().events.map((event) => event.eventType)).toEqual([
      "playing_change",
      "pause_command",
      "pause_command"
    ]);
  });

  it("calculates playing and first-frame latency for the active video once", () => {
    const clock = createClock();
    const observer = createHomeFeedPlaybackObserver({
      now: clock.now,
      log: () => {}
    });

    observer.record({
      eventType: "feed_active_item_change",
      videoId: "ep02",
      pageIndex: 1,
      activeIndex: 1
    });
    clock.advance(40);
    observer.record({
      eventType: "playing_change",
      videoId: "ep02",
      pageIndex: 1,
      activeIndex: 1,
      details: { isPlaying: true }
    });
    clock.advance(35);
    observer.record({
      eventType: "first_frame_render",
      videoId: "ep02",
      pageIndex: 1,
      activeIndex: 1
    });
    clock.advance(50);
    observer.record({
      eventType: "first_frame_render",
      videoId: "ep02",
      pageIndex: 1,
      activeIndex: 1
    });

    expect(observer.getSnapshot().switchMetrics).toEqual({
      videoId: "ep02",
      pageIndex: 1,
      activeChangedAtMs: 1000,
      playingLatencyMs: 40,
      firstFrameLatencyMs: 75
    });
  });

  it("calculates switch latency from early playback ownership changes", () => {
    const clock = createClock();
    const observer = createHomeFeedPlaybackObserver({
      now: clock.now,
      log: () => {}
    });

    observer.record({
      eventType: "feed_playback_owner_change",
      videoId: "ep02",
      pageIndex: 1,
      activeIndex: 1,
      details: { reason: "drag_release" }
    });
    clock.advance(24);
    observer.record({
      eventType: "playing_change",
      videoId: "ep02",
      pageIndex: 1,
      details: { isPlaying: true }
    });

    expect(observer.getSnapshot().switchMetrics).toEqual({
      videoId: "ep02",
      pageIndex: 1,
      activeChangedAtMs: 1000,
      playingLatencyMs: 24
    });
  });

  it("updates page summaries from lifecycle and player state events", () => {
    const observer = createHomeFeedPlaybackObserver({ log: () => {} });

    observer.record({ eventType: "page_mount", videoId: "ep01", pageIndex: 0 });
    observer.record({
      eventType: "preload_state_change",
      videoId: "ep01",
      pageIndex: 0,
      details: { isPreloaded: true }
    });
    observer.record({
      eventType: "playback_ownership_change",
      videoId: "ep01",
      pageIndex: 0,
      details: { hasPlaybackOwnership: true }
    });
    observer.record({
      eventType: "status_change",
      videoId: "ep01",
      pageIndex: 0,
      details: { status: "readyToPlay" }
    });
    observer.record({
      eventType: "playing_change",
      videoId: "ep01",
      pageIndex: 0,
      details: { isPlaying: true }
    });
    observer.record({
      eventType: "muted_change",
      videoId: "ep01",
      pageIndex: 0,
      details: { isMuted: false }
    });

    expect(observer.getSnapshot().pages).toEqual([
      {
        videoId: "ep01",
        pageIndex: 0,
        isMounted: true,
        isPreloaded: true,
        hasPlaybackOwnership: true,
        playerStatus: "readyToPlay",
        isPlaying: true,
        isMuted: false
      }
    ]);
  });

  it("clears events, page summaries, and switch metrics", () => {
    const observer = createHomeFeedPlaybackObserver({ log: () => {} });
    observer.record({
      eventType: "feed_active_item_change",
      videoId: "ep01",
      pageIndex: 0,
      activeIndex: 0
    });
    observer.record({ eventType: "page_mount", videoId: "ep01", pageIndex: 0 });

    observer.clear();

    expect(observer.getSnapshot()).toEqual({
      events: [],
      pages: [],
      activeIndex: undefined,
      activeVideoId: undefined,
      switchMetrics: undefined
    });
  });

  it("continues recording when the logger throws", () => {
    const observer = createHomeFeedPlaybackObserver({
      log: () => {
        throw new Error("logger failed");
      }
    });

    expect(() => observer.record({ eventType: "feed_scroll_begin" })).not.toThrow();
    expect(observer.getSnapshot().events).toHaveLength(1);
  });
});

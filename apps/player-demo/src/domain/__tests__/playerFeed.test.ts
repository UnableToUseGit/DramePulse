import { findNextEpisodeIndex, getFeedPageIndex, getFeedPlaybackMode, getSeriesKey } from "../playerFeed";
import type { PlayerVideo } from "../playerApi";

function makeVideo(overrides: Partial<PlayerVideo>): PlayerVideo {
  return {
    videoId: "video",
    title: "短剧",
    plotSummary: "剧情",
    duration: 60,
    streamUrl: "http://localhost/video.mp4",
    danmakuUrl: "http://localhost/danmaku",
    ...overrides
  };
}

describe("playerFeed", () => {
  it("rounds vertical scroll offset to the nearest feed page", () => {
    expect(getFeedPageIndex({ offsetY: 0, pageHeight: 800, itemCount: 3 })).toBe(0);
    expect(getFeedPageIndex({ offsetY: 799, pageHeight: 800, itemCount: 3 })).toBe(1);
    expect(getFeedPageIndex({ offsetY: 1601, pageHeight: 800, itemCount: 3 })).toBe(2);
  });

  it("clamps feed page index to available videos", () => {
    expect(getFeedPageIndex({ offsetY: -120, pageHeight: 800, itemCount: 3 })).toBe(0);
    expect(getFeedPageIndex({ offsetY: 2600, pageHeight: 800, itemCount: 3 })).toBe(2);
    expect(getFeedPageIndex({ offsetY: 400, pageHeight: 800, itemCount: 0 })).toBe(0);
  });

  it("shows the manual start entry only before the feed experience has started", () => {
    expect(getFeedPlaybackMode({ hasStartedFeed: false, isActive: true })).toEqual({
      shouldShowStartEntry: true,
      shouldAutoStart: false
    });
    expect(getFeedPlaybackMode({ hasStartedFeed: true, isActive: true })).toEqual({
      shouldShowStartEntry: false,
      shouldAutoStart: true
    });
    expect(getFeedPlaybackMode({ hasStartedFeed: true, isActive: false })).toEqual({
      shouldShowStartEntry: false,
      shouldAutoStart: false
    });
  });

  it("builds stable series keys from series id before series name", () => {
    expect(getSeriesKey(makeVideo({ seriesId: "s1", seriesName: "短剧 A" }))).toBe("id:s1");
    expect(getSeriesKey(makeVideo({ seriesName: "短剧 A" }))).toBe("name:短剧 A");
    expect(getSeriesKey(makeVideo({}))).toBeUndefined();
  });

  it("finds the next episode in the same series", () => {
    const videos = [
      makeVideo({ videoId: "s1e1", seriesId: "s1" }),
      makeVideo({ videoId: "other", seriesId: "s2" }),
      makeVideo({ videoId: "s1e2", seriesId: "s1" })
    ];

    expect(findNextEpisodeIndex(videos, 0)).toBe(2);
    expect(findNextEpisodeIndex(videos, 1)).toBeUndefined();
    expect(findNextEpisodeIndex(videos, 99)).toBeUndefined();
  });
});

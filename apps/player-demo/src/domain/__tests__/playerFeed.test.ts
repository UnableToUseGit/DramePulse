import {
  findNextEpisodeIndex,
  getFeedPageIndex,
  getResumePlaybackTime,
  getVideoPlaybackState,
  getSeriesKey,
  shouldPreloadFeedPage
} from "../playerFeed";
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

  it("derives video commands from user intent without treating inactive pages as user pauses", () => {
    expect(getVideoPlaybackState({ isActive: true, userPlaybackIntent: "playing" })).toEqual({
      isStarted: true,
      shouldPlay: true,
      shouldShowPauseHint: false
    });
    expect(getVideoPlaybackState({ isActive: false, userPlaybackIntent: "playing" })).toEqual({
      isStarted: true,
      shouldPlay: false,
      shouldShowPauseHint: false
    });
    expect(getVideoPlaybackState({ isActive: true, userPlaybackIntent: "paused" })).toEqual({
      isStarted: true,
      shouldPlay: false,
      shouldShowPauseHint: true
    });
    expect(getVideoPlaybackState({ isActive: false, userPlaybackIntent: "paused" })).toEqual({
      isStarted: true,
      shouldPlay: false,
      shouldShowPauseHint: false
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

  it("preloads the active feed page and its direct neighbors", () => {
    expect(shouldPreloadFeedPage({ pageIndex: 0, activeIndex: 0 })).toBe(true);
    expect(shouldPreloadFeedPage({ pageIndex: 1, activeIndex: 0 })).toBe(true);
    expect(shouldPreloadFeedPage({ pageIndex: 2, activeIndex: 0 })).toBe(false);

    expect(shouldPreloadFeedPage({ pageIndex: 1, activeIndex: 2 })).toBe(true);
    expect(shouldPreloadFeedPage({ pageIndex: 2, activeIndex: 2 })).toBe(true);
    expect(shouldPreloadFeedPage({ pageIndex: 3, activeIndex: 2 })).toBe(true);
    expect(shouldPreloadFeedPage({ pageIndex: 4, activeIndex: 2 })).toBe(false);
  });

  it("resumes saved playback time unless it is too close to the end", () => {
    expect(getResumePlaybackTime({ savedTime: undefined, duration: 60 })).toBe(0);
    expect(getResumePlaybackTime({ savedTime: 30, duration: 60 })).toBe(30);
    expect(getResumePlaybackTime({ savedTime: -4, duration: 60 })).toBe(0);
    expect(getResumePlaybackTime({ savedTime: 59, duration: 60 })).toBe(0);
    expect(getResumePlaybackTime({ savedTime: 59, duration: 0 })).toBe(59);
  });
});

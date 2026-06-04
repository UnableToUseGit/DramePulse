import {
  buildPlayerFeedItems,
  findNextEpisodeIndex,
  flushBufferedPlaybackPosition,
  getFeedPageIndex,
  getFeedReleaseTargetIndex,
  getFeedVisualLayout,
  getFeedScrollEnabled,
  getNextEpisodeInfoByIndex,
  getRequestedVideoFeedIndex,
  getResumePlaybackTime,
  getTimelineChromeVisibility,
  getVideoPlaybackState,
  getSeriesKey,
  getVideoIndex,
  getSeriesResumeTarget,
  groupVideosBySeries,
  shouldRestoreScrollOffset,
  shouldStartEdgeBackSwipe,
  shouldPreloadFeedPage,
  stagePlaybackPositionUpdate
} from "../playerFeed";
import type { PlayerVideo } from "../playerApi";
import type { RoleCommerceFeedAd } from "../roleCommerceAds";

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

function makeAd(overrides: Partial<RoleCommerceFeedAd> = {}): RoleCommerceFeedAd {
  return {
    adId: "rc1",
    campaignId: "campaign1",
    placement: "after_first_video",
    sponsorLabel: "广告",
    characterName: "太奶奶",
    productName: "云雾哑光口红",
    title: "太奶奶亲自挑的气色口红",
    hook: "别让气色输在第一眼。",
    productDescription: "太奶奶同款短剧番外推荐。",
    voiceoverLines: ["这支颜色，提气色，不张扬。"],
    sellingPoints: ["显气色"],
    priceText: "到手价 99 元",
    ctaText: "查看同款",
    ...overrides
  };
}

describe("playerFeed", () => {
  it("rounds vertical scroll offset to the nearest feed page", () => {
    expect(getFeedPageIndex({ offsetY: 0, pageHeight: 800, itemCount: 3 })).toBe(0);
    expect(getFeedPageIndex({ offsetY: 799, pageHeight: 800, itemCount: 3 })).toBe(1);
    expect(getFeedPageIndex({ offsetY: 1601, pageHeight: 800, itemCount: 3 })).toBe(2);
  });

  it("predicts the release target page from native target offset when available", () => {
    expect(
      getFeedReleaseTargetIndex({
        activeIndex: 0,
        itemCount: 4,
        offsetY: 460,
        pageHeight: 800,
        targetOffsetY: 800
      })
    ).toBe(1);
  });

  it("falls back to the current release offset when native target offset is unavailable", () => {
    expect(
      getFeedReleaseTargetIndex({
        activeIndex: 0,
        itemCount: 4,
        offsetY: 560,
        pageHeight: 800
      })
    ).toBe(1);

    expect(
      getFeedReleaseTargetIndex({
        activeIndex: 1,
        itemCount: 4,
        offsetY: 970,
        pageHeight: 800
      })
    ).toBe(1);
  });

  it("uses release velocity to predict the next page when target offset is unavailable", () => {
    expect(
      getFeedReleaseTargetIndex({
        activeIndex: 1,
        itemCount: 4,
        offsetY: 930,
        pageHeight: 800,
        velocityY: 1.2
      })
    ).toBe(2);

    expect(
      getFeedReleaseTargetIndex({
        activeIndex: 1,
        itemCount: 4,
        offsetY: 1460,
        pageHeight: 800,
        velocityY: -1.2
      })
    ).toBe(0);
  });

  it("clamps feed page index to available videos", () => {
    expect(getFeedPageIndex({ offsetY: -120, pageHeight: 800, itemCount: 3 })).toBe(0);
    expect(getFeedPageIndex({ offsetY: 2600, pageHeight: 800, itemCount: 3 })).toBe(2);
    expect(getFeedPageIndex({ offsetY: 400, pageHeight: 800, itemCount: 0 })).toBe(0);
  });

  it("keeps video above the bottom dock while preserving full-page feed height", () => {
    expect(getFeedVisualLayout({ pageHeight: 800, mode: "home" })).toEqual({
      bottomDockHeight: 74,
      controlsBottomOffset: 72,
      metaBottomOffset: 118,
      actionRailBottomOffset: 124,
      videoHeight: 726
    });
    expect(getFeedVisualLayout({ pageHeight: 800, mode: "series", hasSeriesEpisodeBar: true })).toEqual({
      bottomDockHeight: 96,
      controlsBottomOffset: 94,
      metaBottomOffset: 140,
      actionRailBottomOffset: 146,
      videoHeight: 704
    });
    expect(getFeedVisualLayout({ pageHeight: 60, mode: "home" }).videoHeight).toBe(1);
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

  it("builds role commerce ads only for a series feed", () => {
    const videos = [makeVideo({ videoId: "s1e1" }), makeVideo({ videoId: "s1e2" })];
    const ad = makeAd();

    expect(buildPlayerFeedItems({ videos, roleCommerceAds: [ad], mode: "home" }).map((item) => item.itemId)).toEqual([
      "video:s1e1",
      "video:s1e2"
    ]);
    expect(buildPlayerFeedItems({ videos, roleCommerceAds: [ad], mode: "series" }).map((item) => item.itemId)).toEqual([
      "video:s1e1",
      "role-commerce:rc1",
      "video:s1e2"
    ]);
  });

  it("requests feed navigation only when a new target video differs from the active item", () => {
    const videos = [makeVideo({ videoId: "s1e1" }), makeVideo({ videoId: "s1e2" })];
    const items = buildPlayerFeedItems({ videos, roleCommerceAds: [makeAd()], mode: "series" });

    expect(
      getRequestedVideoFeedIndex({
        items,
        previousRequestedVideoId: "s1e1",
        requestedVideoId: "s1e2",
        activeIndex: 0
      })
    ).toBe(2);
    expect(
      getRequestedVideoFeedIndex({
        items,
        previousRequestedVideoId: "s1e1",
        requestedVideoId: "s1e2",
        activeIndex: 2
      })
    ).toBeUndefined();
    expect(
      getRequestedVideoFeedIndex({
        items,
        previousRequestedVideoId: "s1e1",
        requestedVideoId: "s1e1",
        activeIndex: 1
      })
    ).toBeUndefined();
    expect(
      getRequestedVideoFeedIndex({
        items,
        previousRequestedVideoId: "s1e1",
        requestedVideoId: "missing",
        activeIndex: 0
      })
    ).toBeUndefined();
  });

  it("precomputes next episode labels for each feed item", () => {
    const videos = [
      makeVideo({ videoId: "s1e1", seriesId: "s1", episodeLabel: "ep01" }),
      makeVideo({ videoId: "other", seriesId: "s2", episodeLabel: "ep01" }),
      makeVideo({ videoId: "s1e2", seriesId: "s1", episodeLabel: "ep02" })
    ];

    expect(getNextEpisodeInfoByIndex(videos)).toEqual([
      { hasNextEpisode: true, nextEpisodeLabel: "ep02" },
      { hasNextEpisode: false, nextEpisodeLabel: undefined },
      { hasNextEpisode: false, nextEpisodeLabel: undefined }
    ]);
  });

  it("resolves the selected video index with a safe fallback", () => {
    const videos = [makeVideo({ videoId: "s1e1" }), makeVideo({ videoId: "s1e2" }), makeVideo({ videoId: "s1e3" })];

    expect(getVideoIndex(videos, "s1e3")).toBe(2);
    expect(getVideoIndex(videos, "missing")).toBe(0);
    expect(getVideoIndex(videos, undefined)).toBe(0);
  });

  it("starts back swipe only from the left edge with a rightward horizontal gesture", () => {
    expect(shouldStartEdgeBackSwipe({ startX: 12, startY: 300, screenHeight: 800, deltaX: 32, deltaY: 4 })).toBe(true);
    expect(shouldStartEdgeBackSwipe({ startX: 36, startY: 300, screenHeight: 800, deltaX: 80, deltaY: 2 })).toBe(false);
    expect(shouldStartEdgeBackSwipe({ startX: 12, startY: 300, screenHeight: 800, deltaX: -50, deltaY: 2 })).toBe(false);
    expect(shouldStartEdgeBackSwipe({ startX: 12, startY: 300, screenHeight: 800, deltaX: 20, deltaY: 2 })).toBe(false);
    expect(shouldStartEdgeBackSwipe({ startX: 12, startY: 300, screenHeight: 800, deltaX: 80, deltaY: 70 })).toBe(false);
    expect(shouldStartEdgeBackSwipe({ startX: 12, startY: 742, screenHeight: 800, deltaX: 80, deltaY: 2 })).toBe(false);
  });

  it("restores theater scroll only when the saved offset is meaningful", () => {
    expect(shouldRestoreScrollOffset({ offset: 0, itemCount: 4 })).toBe(false);
    expect(shouldRestoreScrollOffset({ offset: 12, itemCount: 4 })).toBe(false);
    expect(shouldRestoreScrollOffset({ offset: 120, itemCount: 0 })).toBe(false);
    expect(shouldRestoreScrollOffset({ offset: 120, itemCount: 4 })).toBe(true);
  });

  it("groups videos by series and sorts episodes by episode number", () => {
    const videos = [
      makeVideo({ videoId: "s1e2", seriesId: "s1", seriesName: "短剧 A", episodeNo: 2, episodeLabel: "第2集" }),
      makeVideo({ videoId: "s2e1", seriesId: "s2", seriesName: "短剧 B", episodeNo: 1 }),
      makeVideo({ videoId: "s1e1", seriesId: "s1", seriesName: "短剧 A", episodeNo: 1, plotSummary: "A 简介" })
    ];

    const series = groupVideosBySeries(videos);

    expect(series).toHaveLength(2);
    expect(series[0]).toMatchObject({
      seriesKey: "id:s1",
      title: "短剧 A",
      episodeCount: 2,
      summary: "A 简介"
    });
    expect(series[0].episodes.map((episode) => episode.videoId)).toEqual(["s1e1", "s1e2"]);
    expect(series[1].seriesKey).toBe("id:s2");
  });

  it("resolves a series resume target from session records", () => {
    const videos = [
      makeVideo({ videoId: "s1e1", seriesId: "s1", episodeNo: 1 }),
      makeVideo({ videoId: "s1e2", seriesId: "s1", episodeNo: 2 })
    ];
    const [series] = groupVideosBySeries(videos);

    expect(
      getSeriesResumeTarget({
        series,
        seriesResumeVideoIds: {},
        playbackPositions: {}
      })
    ).toEqual({ video: videos[0], time: 0 });

    expect(
      getSeriesResumeTarget({
        series,
        seriesResumeVideoIds: { [series.seriesKey]: "s1e2" },
        playbackPositions: { s1e2: 23 }
      })
    ).toEqual({ video: videos[1], time: 23 });
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

  it("keeps app tabs visible while hiding video metadata chrome during timeline dragging", () => {
    expect(getTimelineChromeVisibility({ isTimelineDragging: false })).toEqual({
      showActionRail: true,
      showMeta: true,
      showBottomTabs: true
    });
    expect(getTimelineChromeVisibility({ isTimelineDragging: true })).toEqual({
      showActionRail: false,
      showMeta: false,
      showBottomTabs: true
    });
  });

  it("disables feed scrolling while timeline dragging is active", () => {
    expect(getFeedScrollEnabled({ isTimelineDragging: false })).toBe(true);
    expect(getFeedScrollEnabled({ isTimelineDragging: true })).toBe(false);
  });

  it("buffers playback position updates while the feed is dragging", () => {
    expect(
      stagePlaybackPositionUpdate({
        isFeedDragging: true,
        playbackPositions: { ep01: 8 },
        videoId: "ep01",
        time: 9
      })
    ).toEqual({
      bufferedPosition: { videoId: "ep01", time: 9 },
      nextPlaybackPositions: { ep01: 8 },
      shouldPublish: false
    });
  });

  it("flushes a buffered playback position after feed dragging ends", () => {
    expect(
      flushBufferedPlaybackPosition({
        bufferedPosition: { videoId: "ep01", time: 9 },
        playbackPositions: { ep01: 8, ep02: 3 }
      })
    ).toEqual({
      bufferedPosition: undefined,
      nextPlaybackPositions: { ep01: 9, ep02: 3 },
      shouldPublish: true
    });
  });
});

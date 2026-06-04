import { getFeedPlaybackPageState } from "../feedPlaybackCoordinator";
import type { PlayerFeedItem } from "../playerFeed";
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

function makeVideoItem(video: PlayerVideo): PlayerFeedItem {
  return {
    itemType: "video",
    itemId: `video:${video.videoId}`,
    video
  };
}

describe("feedPlaybackCoordinator", () => {
  it("marks active, preload, and parked video pages with explicit playback roles", () => {
    const activeVideo = makeVideo({ videoId: "ep02" });
    const preloadVideo = makeVideo({ videoId: "ep01" });
    const parkedVideo = makeVideo({ videoId: "ep04" });

    expect(
      getFeedPlaybackPageState({
        item: makeVideoItem(activeVideo),
        pageIndex: 1,
        activeIndex: 1,
        playbackPositions: {}
      })
    ).toMatchObject({
      pageRole: "active",
      shouldPrepareVideo: true,
      shouldOwnPlayback: true,
      resumeTime: 0
    });

    expect(
      getFeedPlaybackPageState({
        item: makeVideoItem(preloadVideo),
        pageIndex: 0,
        activeIndex: 1,
        playbackPositions: { ep01: 12 }
      })
    ).toMatchObject({
      pageRole: "preload",
      shouldPrepareVideo: true,
      shouldOwnPlayback: false,
      resumeTime: 12
    });

    expect(
      getFeedPlaybackPageState({
        item: makeVideoItem(parkedVideo),
        pageIndex: 3,
        activeIndex: 1,
        playbackPositions: { ep04: 18 }
      })
    ).toMatchObject({
      pageRole: "parked",
      shouldPrepareVideo: false,
      shouldOwnPlayback: false,
      resumeTime: 18
    });
  });

  it("resets resume time for prepared video pages that were saved near the end", () => {
    const video = makeVideo({ videoId: "ep01", duration: 60 });

    expect(
      getFeedPlaybackPageState({
        item: makeVideoItem(video),
        pageIndex: 0,
        activeIndex: 1,
        playbackPositions: { ep01: 59 }
      }).resumeTime
    ).toBe(0);
  });
});

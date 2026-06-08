import { createPlaybackAssetCache } from "../playbackAssetCache";
import { preloadInitialPlaybackAssets, prefetchSeriesCovers, prefetchStoryboardSheets } from "../playbackAssetPreloader";

const storyboard = {
  videoId: "v1",
  intervalSeconds: 1,
  frameWidth: 120,
  frameHeight: 212,
  columns: 5,
  rows: 5,
  sheets: [
    { url: "http://cdn.test/v1/sheet_000.jpg", startTime: 0, frameCount: 25 },
    { url: "http://cdn.test/v1/sheet_001.jpg", startTime: 25, frameCount: 25 }
  ]
};

describe("playbackAssetPreloader", () => {
  it("prefetches every storyboard sheet by default so scrubbing does not wait on late sheets", async () => {
    const cache = createPlaybackAssetCache();
    const prefetchImage = jest.fn(async () => true);
    const manySheetStoryboard = {
      ...storyboard,
      sheets: Array.from({ length: 8 }, (_, index) => ({
        url: `http://cdn.test/v1/sheet_${index.toString().padStart(3, "0")}.jpg`,
        startTime: index * 25,
        frameCount: 25
      }))
    };

    await prefetchStoryboardSheets({
      cache,
      videoId: "v1",
      storyboard: manySheetStoryboard,
      prefetchImage
    });

    expect(prefetchImage).toHaveBeenCalledTimes(8);
    expect(prefetchImage).toHaveBeenLastCalledWith("http://cdn.test/v1/sheet_007.jpg");
  });

  it("prefetches the leading storyboard sheets once and records cache state", async () => {
    const cache = createPlaybackAssetCache();
    const prefetchImage = jest.fn(async () => true);

    await prefetchStoryboardSheets({
      cache,
      videoId: "v1",
      storyboard,
      limit: 2,
      prefetchImage
    });
    await prefetchStoryboardSheets({
      cache,
      videoId: "v1",
      storyboard,
      limit: 2,
      prefetchImage
    });

    expect(prefetchImage).toHaveBeenCalledTimes(2);
    expect(prefetchImage).toHaveBeenCalledWith("http://cdn.test/v1/sheet_000.jpg");
    expect(prefetchImage).toHaveBeenCalledWith("http://cdn.test/v1/sheet_001.jpg");
    expect(cache.hasPrefetchedStoryboardSheet("v1", "http://cdn.test/v1/sheet_000.jpg")).toBe(true);
    expect(cache.hasPrefetchedStoryboardSheet("v1", "http://cdn.test/v1/sheet_001.jpg")).toBe(true);
  });

  it("preloads first video storyboard and interaction plans without danmaku or playback-assets", async () => {
    const cache = createPlaybackAssetCache();
    const calls: string[] = [];
    const fetcher = jest.fn(async (url: string) => {
      calls.push(url);
      if (url.endsWith("/storyboard")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            video_id: "v1",
            available: true,
            interval_seconds: 1,
            frame_width: 120,
            frame_height: 212,
            columns: 5,
            rows: 5,
            sheets: [{ url: "/storyboards/v1/sheet_000.jpg", start_time: 0, frame_count: 25 }]
          })
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ interaction_plans: [{ interaction_id: "i1" }] })
      };
    });
    const prefetchImage = jest.fn(async () => true);

    await preloadInitialPlaybackAssets({
      apiBaseUrl: "http://api.test",
      cache,
      videoId: "v1",
      fetcher,
      prefetchImage
    });

    expect(calls).toEqual([
      "http://api.test/api/videos/v1/storyboard",
      "http://api.test/api/videos/v1/interaction-plans"
    ]);
    expect(calls.some((url) => url.includes("danmaku") || url.includes("playback-assets"))).toBe(false);
    expect(cache.get("v1")?.storyboard?.sheets[0]?.url).toBe("http://api.test/storyboards/v1/sheet_000.jpg");
    expect(cache.get("v1")?.interactionPlans).toEqual([{ interaction_id: "i1" }]);
    expect(prefetchImage).toHaveBeenCalledWith("http://api.test/storyboards/v1/sheet_000.jpg");
  });

  it("prefetches only the leading theater cover images", async () => {
    const prefetchImage = jest.fn(async () => true);

    await prefetchSeriesCovers({
      series: [
        { coverUrl: "http://cdn.test/1.jpg" },
        { coverUrl: "http://cdn.test/2.jpg" },
        { coverUrl: "http://cdn.test/3.jpg" }
      ],
      limit: 2,
      prefetchImage
    });

    expect(prefetchImage).toHaveBeenCalledTimes(2);
    expect(prefetchImage).toHaveBeenNthCalledWith(1, "http://cdn.test/1.jpg");
    expect(prefetchImage).toHaveBeenNthCalledWith(2, "http://cdn.test/2.jpg");
  });
});

import { createPlaybackAssetCache } from "../playbackAssetCache";

const storyboard = {
  videoId: "v1",
  intervalSeconds: 1,
  frameWidth: 120,
  frameHeight: 212,
  columns: 5,
  rows: 5,
  sheets: [{ url: "http://cdn.test/sheet_000.jpg", startTime: 0, frameCount: 25 }]
};

describe("playbackAssetCache", () => {
  it("stores lightweight playback assets per video", () => {
    const cache = createPlaybackAssetCache();

    cache.setStoryboard("v1", storyboard);
    cache.setInteractionPlans("v1", [{ interaction_id: "i1" }]);
    cache.markStoryboardSheetPrefetched("v1", "http://cdn.test/sheet_000.jpg");

    expect(cache.get("v1")).toMatchObject({
      storyboard,
      interactionPlans: [{ interaction_id: "i1" }]
    });
    expect(cache.hasPrefetchedStoryboardSheet("v1", "http://cdn.test/sheet_000.jpg")).toBe(true);
  });

  it("prunes cached assets outside the active video window", () => {
    const cache = createPlaybackAssetCache();
    cache.setStoryboard("v1", storyboard);
    cache.setStoryboard("v2", { ...storyboard, videoId: "v2" });

    cache.prune(["v2"]);

    expect(cache.get("v1")).toBeUndefined();
    expect(cache.get("v2")?.storyboard?.videoId).toBe("v2");
  });
});

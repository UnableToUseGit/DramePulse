import {
  buildVideoStageSource,
  FEED_VIDEO_BUFFER_OPTIONS,
  FEED_VIDEO_SOURCE_CACHING_ENABLED
} from "../videoSource";

describe("videoSource", () => {
  it("enables caching for remote feed video sources", () => {
    expect(
      buildVideoStageSource({
        enableCaching: true,
        streamUrl: "http://localhost:8000/api/videos/ep01/stream"
      })
    ).toEqual({
      uri: "http://localhost:8000/api/videos/ep01/stream",
      useCaching: true,
      contentType: "progressive"
    });
  });

  it("keeps local asset sources unchanged", () => {
    expect(
      buildVideoStageSource({
        enableCaching: true,
        streamUrl: 42
      })
    ).toBe(42);
  });

  it("uses a bounded forward buffer for feed videos", () => {
    expect(FEED_VIDEO_BUFFER_OPTIONS).toEqual({
      maxBufferBytes: 24 * 1024 * 1024,
      minBufferForPlayback: 1,
      preferredForwardBufferDuration: 8,
      prioritizeTimeOverSizeThreshold: true,
      waitsToMinimizeStalling: false
    });
  });

  it("keeps feed source caching disabled by default", () => {
    expect(FEED_VIDEO_SOURCE_CACHING_ENABLED).toBe(false);
  });
});

import { createPlaybackAssetCache } from "../playbackAssetCache";
import { loadStartupData } from "../startupLoader";

function createFetcher(responses: Record<string, unknown>) {
  const calls: string[] = [];
  const fetcher = jest.fn(async (url: string) => {
    calls.push(url);
    const payload = responses[url];
    if (payload === undefined) {
      return {
        ok: false,
        status: 404,
        json: async () => ({})
      };
    }
    return {
      ok: true,
      status: 200,
      json: async () => payload
    };
  });
  return { fetcher, calls };
}

describe("startupLoader", () => {
  it("loads feed, series, first video lightweight assets, and leading covers without episodes or danmaku", async () => {
    const cache = createPlaybackAssetCache();
    const { fetcher, calls } = createFetcher({
      "http://api.test/api/feed/home": {
        videos: [
          {
            video_id: "v1",
            series_id: "s1",
            series_name: "短剧 A",
            title: "短剧 A 第1集",
            stream_url: "/api/videos/v1/stream",
            danmaku_url: "/api/videos/v1/danmaku"
          }
        ]
      },
      "http://api.test/api/series": {
        series: [
          {
            series_id: "s1",
            title: "短剧 A",
            cover_url: "/covers/s1.jpg",
            episode_count: 2,
            first_video_id: "v1",
            status: "active"
          }
        ]
      },
      "http://api.test/api/videos/v1/storyboard": {
        video_id: "v1",
        available: true,
        interval_seconds: 1,
        frame_width: 120,
        frame_height: 212,
        columns: 5,
        rows: 5,
        sheets: [{ url: "/storyboards/v1/sheet_000.jpg", start_time: 0, frame_count: 25 }]
      },
      "http://api.test/api/videos/v1/story-chapters": {
        video_id: "v1",
        available: true,
        chapters: [{ chapter_id: "c1", video_id: "v1", start_time: 0, end_time: 30, title: "开场" }]
      },
      "http://api.test/api/videos/v1/interaction-assets": {
        video_id: "v1",
        available: true,
        items: [{ interaction_id: "ia1", video_id: "v1", interaction_mode: "inner_voice_danmaku", trigger_time: 12 }]
      }
    });
    const prefetchImage = jest.fn(async () => true);

    const startup = await loadStartupData({
      apiBaseUrl: "http://api.test",
      cache,
      fetcher,
      prefetchImage
    });

    expect(startup.homeVideos.map((video) => video.videoId)).toEqual(["v1"]);
    expect(startup.theaterSeries.map((series) => series.seriesKey)).toEqual(["id:s1"]);
    expect(cache.get("v1")?.storyboard?.sheets[0]?.url).toBe("http://api.test/storyboards/v1/sheet_000.jpg");
    expect(prefetchImage).toHaveBeenCalledWith("http://api.test/covers/s1.jpg");
    expect(prefetchImage).toHaveBeenCalledWith("http://api.test/storyboards/v1/sheet_000.jpg");
    expect(calls).toEqual([
      "http://api.test/api/feed/home",
      "http://api.test/api/series",
      "http://api.test/api/videos/v1/storyboard",
      "http://api.test/api/videos/v1/story-chapters",
      "http://api.test/api/videos/v1/interaction-assets"
    ]);
    expect(calls.some((url) => url.includes("/episodes") || url.includes("danmaku") || url.includes("playback-assets"))).toBe(false);
  });

  it("can skip startup preloads for fast UI iteration", async () => {
    const cache = createPlaybackAssetCache();
    const { fetcher, calls } = createFetcher({
      "http://api.test/api/feed/home": {
        videos: [
          {
            video_id: "v1",
            series_id: "s1",
            series_name: "短剧 A",
            title: "短剧 A 第1集",
            stream_url: "/api/videos/v1/stream",
            danmaku_url: "/api/videos/v1/danmaku"
          }
        ]
      },
      "http://api.test/api/series": {
        series: [
          {
            series_id: "s1",
            title: "短剧 A",
            cover_url: "/covers/s1.jpg",
            episode_count: 2,
            first_video_id: "v1",
            status: "active"
          }
        ]
      }
    });
    const prefetchImage = jest.fn(async () => true);

    const startup = await loadStartupData({
      apiBaseUrl: "http://api.test",
      cache,
      fetcher,
      prefetchImage,
      skipPreload: true
    });

    expect(startup.homeVideos.map((video) => video.videoId)).toEqual(["v1"]);
    expect(startup.theaterSeries.map((series) => series.seriesKey)).toEqual(["id:s1"]);
    expect(cache.get("v1")).toBeUndefined();
    expect(prefetchImage).not.toHaveBeenCalled();
    expect(calls).toEqual(["http://api.test/api/feed/home", "http://api.test/api/series"]);
  });
});

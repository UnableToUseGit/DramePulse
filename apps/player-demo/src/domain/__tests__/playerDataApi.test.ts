import { loadHomeFeedVideos } from "../playerDataApi";

function createFetcher(responses: Record<string, unknown>) {
  const calls: string[] = [];
  const fetcher = jest.fn(async (url: string) => {
    calls.push(url);
    const payload = responses[url];
    if (payload instanceof Error) {
      throw payload;
    }
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

describe("playerDataApi", () => {
  it("loads home feed from /api/feed/home when available", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/feed/home": {
        videos: [
          {
            video_id: "s1_ep01",
            series_id: "s1",
            series_name: "短剧 A",
            title: "短剧 A 第1集",
            episode_no: 1,
            stream_url: "/api/videos/s1_ep01/stream",
            danmaku_url: "/api/videos/s1_ep01/danmaku"
          }
        ]
      }
    });

    const videos = await loadHomeFeedVideos({ apiBaseUrl: "http://api.test", fetcher });

    expect(videos).toHaveLength(1);
    expect(videos[0]).toMatchObject({
      videoId: "s1_ep01",
      seriesId: "s1",
      episodeNo: 1,
      streamUrl: "http://api.test/api/videos/s1_ep01/stream"
    });
  });

  it("falls back to /api/videos and keeps only the first episode per series", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/feed/home": new Error("feed unavailable"),
      "http://api.test/api/videos": {
        videos: [
          {
            video_id: "s1_ep02",
            series_id: "s1",
            series_name: "短剧 A",
            title: "短剧 A 第2集",
            episode_no: 2,
            stream_url: "/api/videos/s1_ep02/stream",
            danmaku_url: "/api/videos/s1_ep02/danmaku"
          },
          {
            video_id: "s1_ep01",
            series_id: "s1",
            series_name: "短剧 A",
            title: "短剧 A 第1集",
            episode_no: 1,
            stream_url: "/api/videos/s1_ep01/stream",
            danmaku_url: "/api/videos/s1_ep01/danmaku"
          },
          {
            video_id: "s2_ep01",
            series_id: "s2",
            series_name: "短剧 B",
            title: "短剧 B 第1集",
            episode_no: 1,
            stream_url: "/api/videos/s2_ep01/stream",
            danmaku_url: "/api/videos/s2_ep01/danmaku"
          }
        ]
      }
    });

    const videos = await loadHomeFeedVideos({ apiBaseUrl: "http://api.test", fetcher });

    expect(videos.map((video) => video.videoId)).toEqual(["s1_ep01", "s2_ep01"]);
  });
});

import {
  loadHomeFeedVideos,
  loadPlaybackAssets,
  loadSeriesEpisodes,
  loadTheaterSeries
} from "../playerDataApi";

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

  it("filters pseudo series rows from theater series", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/series": {
        series: [
          {
            series_id: "beiwang",
            title: "北往",
            cover_url: "/dramas/beiwang/cover.webp",
            episode_count: 5,
            first_video_id: "beiwang_ep01",
            status: "active"
          },
          {
            series_id: "ep_01",
            title: "第1集",
            cover_url: null,
            episode_count: 1,
            first_video_id: "ep_01",
            status: "active"
          }
        ]
      }
    });

    const series = await loadTheaterSeries({ apiBaseUrl: "http://api.test", fetcher });

    expect(series).toHaveLength(1);
    expect(series[0]).toMatchObject({
      seriesId: "beiwang",
      title: "北往",
      coverUrl: "http://api.test/dramas/beiwang/cover.webp",
      episodeCount: 5,
      firstVideoId: "beiwang_ep01"
    });
  });

  it("loads series episodes from /api/series/{series_id}/episodes", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/series/beiwang/episodes": {
        series_id: "beiwang",
        series_name: "北往",
        episodes: [
          {
            video_id: "beiwang_ep01",
            series_id: "beiwang",
            series_name: "北往",
            title: "北往 第1集",
            episode_no: 1,
            stream_url: "/api/videos/beiwang_ep01/stream",
            danmaku_url: "/api/videos/beiwang_ep01/danmaku"
          }
        ]
      }
    });

    const episodes = await loadSeriesEpisodes({
      apiBaseUrl: "http://api.test",
      seriesId: "beiwang",
      fetcher
    });

    expect(episodes.map((video) => video.videoId)).toEqual(["beiwang_ep01"]);
  });

  it("loads playback assets with safe defaults when optional assets are missing", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/videos/beiwang_ep01": {
        video_id: "beiwang_ep01",
        series_id: "beiwang",
        series_name: "北往",
        title: "北往 第1集",
        episode_no: 1,
        stream_url: "/api/videos/beiwang_ep01/stream",
        danmaku_url: "/api/videos/beiwang_ep01/danmaku"
      },
      "http://api.test/api/videos/beiwang_ep01/interaction-plans": {
        video_id: "beiwang_ep01",
        interaction_plans: []
      }
    });

    const assets = await loadPlaybackAssets({
      apiBaseUrl: "http://api.test",
      videoId: "beiwang_ep01",
      fetcher
    });

    expect(assets.video.videoId).toBe("beiwang_ep01");
    expect(assets.storyChapters).toEqual([]);
    expect(assets.storyboard).toBeUndefined();
    expect(assets.interactionPlans).toEqual([]);
  });
});

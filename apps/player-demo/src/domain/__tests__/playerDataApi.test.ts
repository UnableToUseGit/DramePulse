import {
  loadHomeFeedVideos,
  loadLightweightPlaybackAssets,
  loadVideoInteractionPlans,
  loadVideoStoryboard,
  loadTheaterSeriesGroups,
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
  it("loads home feed directly from /api/feed/home", async () => {
    const { fetcher, calls } = createFetcher({
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
          },
          {
            video_id: "s1_ep02",
            series_id: "s1",
            series_name: "短剧 A",
            title: "短剧 A 第2集",
            episode_no: 2,
            stream_url: "/api/videos/s1_ep02/stream",
            danmaku_url: "/api/videos/s1_ep02/danmaku"
          }
        ]
      }
    });

    const videos = await loadHomeFeedVideos({ apiBaseUrl: "http://api.test", fetcher });

    expect(calls).toEqual(["http://api.test/api/feed/home"]);
    expect(videos.map((video) => video.videoId)).toEqual(["s1_ep01", "s1_ep02"]);
    expect(videos[0]).toMatchObject({
      videoId: "s1_ep01",
      seriesId: "s1",
      episodeNo: 1,
      streamUrl: "http://api.test/api/videos/s1_ep01/stream"
    });
  });

  it("does not fall back to /api/videos when the home feed endpoint is unavailable", async () => {
    const { fetcher, calls } = createFetcher({
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

    await expect(loadHomeFeedVideos({ apiBaseUrl: "http://api.test", fetcher })).rejects.toThrow("feed unavailable");
    expect(calls).toEqual(["http://api.test/api/feed/home"]);
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

  it("loads theater series groups with full episodes from page-level endpoints", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/series": {
        series: [
          {
            series_id: "beiwang",
            title: "北往",
            cover_url: "/dramas/beiwang/cover.webp",
            episode_count: 2,
            first_video_id: "beiwang_ep01",
            status: "active"
          }
        ]
      },
      "http://api.test/api/series/beiwang/episodes": {
        series_id: "beiwang",
        series_name: "北往",
        episodes: [
          {
            video_id: "beiwang_ep02",
            series_id: "beiwang",
            series_name: "北往",
            title: "北往 第2集",
            episode_no: 2,
            stream_url: "/api/videos/beiwang_ep02/stream",
            danmaku_url: "/api/videos/beiwang_ep02/danmaku"
          },
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

    const groups = await loadTheaterSeriesGroups({ apiBaseUrl: "http://api.test", fetcher });

    expect(groups).toHaveLength(1);
    expect(groups[0].seriesKey).toBe("id:beiwang");
    expect(groups[0].coverUrl).toBe("http://api.test/dramas/beiwang/cover.webp");
    expect(groups[0].episodeCount).toBe(2);
    expect(groups[0].episodes.map((video) => video.videoId)).toEqual(["beiwang_ep01", "beiwang_ep02"]);
  });

  it("falls back to /api/videos for theater series groups when series endpoints are empty", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/series": {
        series: []
      },
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
          }
        ]
      }
    });

    const groups = await loadTheaterSeriesGroups({ apiBaseUrl: "http://api.test", fetcher });

    expect(groups).toHaveLength(1);
    expect(groups[0].episodes.map((video) => video.videoId)).toEqual(["s1_ep01", "s1_ep02"]);
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
      "http://api.test/api/videos/beiwang_ep01/storyboard": {
        video_id: "beiwang_ep01",
        available: true,
        interval_seconds: 1,
        frame_width: 120,
        frame_height: 212,
        columns: 5,
        rows: 5,
        sheets: [{ url: "/storyboards/beiwang_ep01/sheet_000.jpg", start_time: 0, frame_count: 25 }]
      },
      "http://api.test/api/videos/beiwang_ep01/interaction-plans": {
        video_id: "beiwang_ep01",
        interaction_plans: []
      }
    });

    const assets = await loadLightweightPlaybackAssets({
      apiBaseUrl: "http://api.test",
      videoId: "beiwang_ep01",
      fetcher
    });

    expect(assets.video.videoId).toBe("beiwang_ep01");
    expect(assets.storyChapters).toEqual([]);
    expect(assets.storyboard?.sheets[0]?.url).toBe("http://api.test/storyboards/beiwang_ep01/sheet_000.jpg");
    expect(assets.video.storyboard?.sheets[0]?.url).toBe("http://api.test/storyboards/beiwang_ep01/sheet_000.jpg");
    expect(assets.interactionPlans).toEqual([]);
  });

  it("loads storyboard without requesting danmaku or playback assets", async () => {
    const { fetcher, calls } = createFetcher({
      "http://api.test/api/videos/beiwang_ep01/storyboard": {
        video_id: "beiwang_ep01",
        available: true,
        interval_seconds: 1,
        frame_width: 120,
        frame_height: 212,
        columns: 5,
        rows: 5,
        sheets: [{ url: "/storyboards/beiwang_ep01/sheet_000.jpg", start_time: 0, frame_count: 25 }]
      }
    });

    const storyboard = await loadVideoStoryboard({
      apiBaseUrl: "http://api.test",
      videoId: "beiwang_ep01",
      fetcher
    });

    expect(storyboard?.sheets[0]?.url).toBe("http://api.test/storyboards/beiwang_ep01/sheet_000.jpg");
    expect(calls).toEqual(["http://api.test/api/videos/beiwang_ep01/storyboard"]);
  });

  it("loads interaction plans without requesting danmaku or playback assets", async () => {
    const { fetcher, calls } = createFetcher({
      "http://api.test/api/videos/beiwang_ep01/interaction-plans": {
        video_id: "beiwang_ep01",
        interaction_plans: [{ interaction_id: "i1" }]
      }
    });

    const plans = await loadVideoInteractionPlans({
      apiBaseUrl: "http://api.test",
      videoId: "beiwang_ep01",
      fetcher
    });

    expect(plans).toEqual([{ interaction_id: "i1" }]);
    expect(calls).toEqual(["http://api.test/api/videos/beiwang_ep01/interaction-plans"]);
  });

  it("falls back to /api/videos when the single video playback asset endpoint is unavailable", async () => {
    const { fetcher } = createFetcher({
      "http://api.test/api/videos/beiwang_ep01": new Error("detail unavailable"),
      "http://api.test/api/videos": {
        videos: [
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
      },
      "http://api.test/api/videos/beiwang_ep01/interaction-plans": {
        video_id: "beiwang_ep01",
        interaction_plans: []
      }
    });

    const assets = await loadLightweightPlaybackAssets({
      apiBaseUrl: "http://api.test",
      videoId: "beiwang_ep01",
      fetcher
    });

    expect(assets.video.videoId).toBe("beiwang_ep01");
    expect(assets.video.streamUrl).toBe("http://api.test/api/videos/beiwang_ep01/stream");
  });
});

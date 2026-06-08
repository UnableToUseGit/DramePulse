import { loadPlayerData, loadPlayerVideos, loadVideoDanmaku, normalizeDanmakuResponse, normalizeVideo } from "../playerApi";

describe("playerApi", () => {
  it("normalizes backend video URLs into absolute player data", () => {
    expect(
      normalizeVideo(
        {
          video_id: "beipai_xunbao_biji_ep63",
          series_id: "beipai_xunbao_biji",
          series_name: "北派寻宝笔记",
          title: "第63集",
          episode_label: "ep63",
          duration: 123.45,
          stream_url: "/api/videos/beipai_xunbao_biji_ep63/stream",
          danmaku_url: "/api/videos/beipai_xunbao_biji_ep63/danmaku",
          story_chapters: [
            {
              chapter_id: "ch_001",
              video_id: "beipai_xunbao_biji_ep63",
              start_time: 0,
              end_time: 12,
              title: "债主堵门",
              summary: "债主上门逼债。",
              importance: 0.7
            }
          ],
          storyboard: {
            video_id: "beipai_xunbao_biji_ep63",
            interval_seconds: 1,
            frame_width: 160,
            frame_height: 90,
            columns: 5,
            rows: 5,
            sheets: [{ url: "/storyboards/beipai_xunbao_biji_ep63/sheet_000.jpg", start_time: 0, frame_count: 25 }]
          }
        },
        "http://127.0.0.1:8000"
      )
    ).toEqual({
      videoId: "beipai_xunbao_biji_ep63",
      seriesId: "beipai_xunbao_biji",
      seriesName: "北派寻宝笔记",
      title: "北派寻宝笔记",
      plotSummary: "第63集",
      episodeLabel: "ep63",
      duration: 123.45,
      streamUrl: "http://127.0.0.1:8000/api/videos/beipai_xunbao_biji_ep63/stream",
      danmakuUrl: "http://127.0.0.1:8000/api/videos/beipai_xunbao_biji_ep63/danmaku",
      storyChapters: [
        {
          chapterId: "ch_001",
          videoId: "beipai_xunbao_biji_ep63",
          startTime: 0,
          endTime: 12,
          title: "债主堵门",
          summary: "债主上门逼债。",
          importance: 0.7
        }
      ],
      storyboard: {
        videoId: "beipai_xunbao_biji_ep63",
        intervalSeconds: 1,
        frameWidth: 160,
        frameHeight: 90,
        columns: 5,
        rows: 5,
        sheets: [
          {
            url: "http://127.0.0.1:8000/storyboards/beipai_xunbao_biji_ep63/sheet_000.jpg",
            startTime: 0,
            frameCount: 25
          }
        ]
      }
    });
  });

  it("normalizes available danmaku and removes empty text", () => {
    const danmaku = normalizeDanmakuResponse({
      available: true,
      items: [
        { danmaku_id: "b", time_sec: 2.2, text: "第二条", digg_count: 1, score: 2 },
        { danmaku_id: "empty", time_sec: 1.5, text: "" },
        { danmaku_id: "a", time_sec: 1, text: "第一条", digg_count: 3, score: 4 }
      ]
    });

    expect(danmaku).toEqual([
      { danmaku_id: "a", time_sec: 1, text: "第一条", digg_count: 3, score: 4 },
      { danmaku_id: "b", time_sec: 2.2, text: "第二条", digg_count: 1, score: 2 }
    ]);
  });

  it("returns empty danmaku when backend marks it unavailable", () => {
    expect(normalizeDanmakuResponse({ available: false, items: [{ time_sec: 1, text: "x" }] })).toEqual([]);
  });

  it("loads the first playable video and leaves danmaku empty without requesting the danmaku URL", async () => {
    const fetcher = jest.fn(async (url: string) => {
      if (url.endsWith("/api/videos")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            videos: [
              {
                video_id: "v1",
                title: "第一集",
                duration: 60,
                stream_url: "/api/videos/v1/stream",
                danmaku_url: "/api/videos/v1/danmaku"
              }
            ]
          })
        };
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const data = await loadPlayerData({ apiBaseUrl: "http://localhost:8000", fetcher });

    expect(data.video.videoId).toBe("v1");
    expect(data.video.streamUrl).toBe("http://localhost:8000/api/videos/v1/stream");
    expect(data.danmaku).toEqual([]);
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/videos", {
      signal: expect.any(AbortSignal)
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("loads every playable video from the backend feed", async () => {
    const fetcher = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        videos: [
          {
            video_id: "v1",
            series_name: "北派寻宝笔记",
            title: "第一集",
            duration: 60,
            stream_url: "/api/videos/v1/stream",
            danmaku_url: "/api/videos/v1/danmaku"
          },
          {
            video_id: "broken",
            title: "缺少视频流",
            danmaku_url: "/api/videos/broken/danmaku"
          },
          {
            video_id: "v2",
            title: "第二集",
            duration: 66,
            stream_url: "/api/videos/v2/stream",
            danmaku_url: "/api/videos/v2/danmaku"
          }
        ]
      })
    }));

    const videos = await loadPlayerVideos({ apiBaseUrl: "http://localhost:8000", fetcher });

    expect(videos.map((video) => video.videoId)).toEqual(["v1", "v2"]);
    expect(videos[1].streamUrl).toBe("http://localhost:8000/api/videos/v2/stream");
    expect(videos[1].danmakuUrl).toBe("http://localhost:8000/api/videos/v2/danmaku");
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/videos", {
      signal: expect.any(AbortSignal)
    });
  });

  it("returns empty danmaku from the selected video without requesting the danmaku URL", async () => {
    const fetcher = jest.fn(async () => {
      throw new Error("danmaku should not be requested");
    });

    const danmaku = await loadVideoDanmaku({
      danmakuUrl: "http://localhost:8000/api/videos/v2/danmaku",
      fetcher
    });

    expect(danmaku).toEqual([]);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

import { askStoryQa, resolveStoryQaContext } from "../storyQa";

describe("storyQa", () => {
  it("posts story Q&A requests to the backend", async () => {
    const fetcher = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ answer: "他是纪家长辈。", sources: [] })
    }));

    const answer = await askStoryQa({
      apiBaseUrl: "http://localhost:8000",
      question: " 他是谁？ ",
      seriesId: "demo",
      currentEpisode: 2,
      currentTime: 22.5,
      fetcher
    });

    expect(answer).toEqual({ answer: "他是纪家长辈。", sources: [] });
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/story-qa/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "他是谁？",
        series_id: "demo",
        current_episode: 2,
        current_time: 22.5
      })
    });
  });

  it("does not send empty questions", async () => {
    const fetcher = jest.fn();

    await expect(
      askStoryQa({
        apiBaseUrl: "/",
        question: "   ",
        seriesId: "demo",
        currentEpisode: 1,
        currentTime: 0,
        fetcher
      })
    ).rejects.toThrow("请输入问题");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("surfaces backend errors for display", async () => {
    const fetcher = jest.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ detail: "LIGHTRAG_WORKING_DIR does not exist" })
    }));

    await expect(
      askStoryQa({
        apiBaseUrl: "http://localhost:8000",
        question: "刚才发生了什么？",
        seriesId: "demo",
        currentEpisode: 1,
        currentTime: 12,
        fetcher
      })
    ).rejects.toThrow("LIGHTRAG_WORKING_DIR does not exist");
  });

  it("resolves series and episode context from video metadata", () => {
    expect(
      resolveStoryQaContext({
        videoId: "v1",
        seriesId: "series-a",
        title: "第一集",
        episodeNo: 3,
        episodeLabel: "ep03",
        duration: 60,
        streamUrl: "/stream",
        danmakuUrl: "/danmaku"
      })
    ).toEqual({ seriesId: "series-a", currentEpisode: 3 });

    expect(
      resolveStoryQaContext({
        videoId: "v2",
        title: "第二集",
        episodeLabel: "ep02",
        duration: 60,
        streamUrl: "/stream",
        danmakuUrl: "/danmaku"
      })
    ).toEqual({ seriesId: "v2", currentEpisode: 2 });
  });
});

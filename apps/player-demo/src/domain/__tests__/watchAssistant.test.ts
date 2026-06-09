import { askWatchAssistant, transcribeWatchAssistantAudio } from "../watchAssistant";

describe("watchAssistant", () => {
  it("posts assistant context and normalizes actions", async () => {
    const fetcher = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        reply: "已准备跳转。",
        actions: [
          { type: "answer", reason: "解释" },
          { type: "seek", target_time: 42, relative_seconds: 10 },
          { type: "next_episode" },
          { type: "pause" },
          { type: "resume" },
          { type: "noop", reason: "无动作" }
        ],
        tool_calls: [{ tool: "seek_relative", arguments: { seconds: 10 }, status: "ok", result: { target_time: 42 } }],
        sources: []
      })
    }));

    const response = await askWatchAssistant({
      apiBaseUrl: "http://localhost:8000",
      message: " 快进 10 秒 ",
      seriesId: "demo",
      videoId: "demo_ep01",
      currentEpisode: 1,
      currentTime: 32,
      duration: 90,
      fetcher
    });

    expect(response.actions.map((action) => action.type)).toEqual(["answer", "seek", "next_episode", "pause", "resume", "noop"]);
    expect(response.actions[1]).toMatchObject({ targetTime: 42, relativeSeconds: 10 });
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/watch-assistant/act", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "快进 10 秒",
        series_id: "demo",
        video_id: "demo_ep01",
        current_episode: 1,
        current_time: 32,
        duration: 90,
        available_tools: ["story_qa", "seek", "seek_relative", "next_episode", "pause", "resume"]
      })
    });
  });

  it("rejects empty messages without calling backend", async () => {
    const fetcher = jest.fn();

    await expect(
      askWatchAssistant({
        apiBaseUrl: "/",
        message: " ",
        seriesId: "demo",
        videoId: "demo_ep01",
        currentEpisode: 1,
        currentTime: 0,
        duration: 60,
        fetcher
      })
    ).rejects.toThrow("请输入指令或剧情问题");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("surfaces backend errors", async () => {
    const fetcher = jest.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ detail: "bad request" })
    }));

    await expect(
      askWatchAssistant({
        apiBaseUrl: "http://localhost:8000",
        message: "下一集",
        seriesId: "demo",
        videoId: "demo_ep01",
        currentEpisode: 1,
        currentTime: 0,
        duration: 60,
        fetcher
      })
    ).rejects.toThrow("bad request");
  });

  it("uploads audio for transcription and normalizes response", async () => {
    const fetcher = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ text: " 暂停 ", confidence: 0.82, language: "zh", duration_ms: 1200 })
    }));

    const response = await transcribeWatchAssistantAudio({
      apiBaseUrl: "http://localhost:8000",
      audioUri: "file:///tmp/watch-assistant.m4a",
      seriesId: "demo",
      videoId: "demo_ep01",
      currentEpisode: 1,
      currentTime: 12,
      duration: 1.2,
      fetcher
    });

    expect(response).toEqual({ text: "暂停", confidence: 0.82, language: "zh", durationMs: 1200 });
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/watch-assistant/transcribe", {
      method: "POST",
      body: expect.any(FormData)
    });
  });

  it("rejects empty transcription results", async () => {
    const fetcher = jest.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ text: " ", confidence: 0, language: "zh", duration_ms: 0 })
    }));

    await expect(
      transcribeWatchAssistantAudio({
        apiBaseUrl: "http://localhost:8000",
        audioUri: "file:///tmp/watch-assistant.m4a",
        seriesId: "demo",
        videoId: "demo_ep01",
        currentEpisode: 1,
        currentTime: 0,
        duration: 0,
        fetcher
      })
    ).rejects.toThrow("没有听清，可以再说一次");
  });
});

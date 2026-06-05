import { createHomeFeedPlaybackFileLogger } from "../homeFeedPlaybackFileLogger";

describe("homeFeedPlaybackFileLogger", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("prints immediately and flushes queued lines to the dev log endpoint", () => {
    const fallbackLog = jest.fn();
    const fetcher = jest.fn().mockResolvedValue({ ok: true });
    const logger = createHomeFeedPlaybackFileLogger({
      apiBaseUrl: "http://localhost:8000",
      fallbackLog,
      fetcher,
      flushDelayMs: 250
    });

    logger("[HomeFeedPlayback] one");
    logger("[HomeFeedPlayback] two");

    expect(fallbackLog).toHaveBeenCalledTimes(2);
    expect(fetcher).not.toHaveBeenCalled();

    jest.advanceTimersByTime(250);

    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/api/dev/home-feed-playback-logs", {
      body: JSON.stringify({ lines: ["[HomeFeedPlayback] one", "[HomeFeedPlayback] two"] }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
  });
});

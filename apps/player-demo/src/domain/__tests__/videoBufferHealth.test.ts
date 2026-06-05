import { getVideoBufferHealthSample } from "../videoBufferHealth";

describe("videoBufferHealth", () => {
  it("records active playback buffer health at a bounded interval", () => {
    expect(
      getVideoBufferHealthSample({
        bufferedPosition: 8.4,
        currentTime: 5.2,
        isPlaying: true,
        lastReportedTime: 3,
        shouldPlay: true
      })
    ).toEqual({
      details: {
        bufferAhead: 3.2,
        bufferedPosition: 8.4,
        currentTime: 5.2,
        isLowBuffer: false
      },
      nextLastReportedTime: 5.2,
      shouldRecord: true
    });
  });

  it("records immediately when playback is close to the buffered edge", () => {
    expect(
      getVideoBufferHealthSample({
        bufferedPosition: 6,
        currentTime: 5.2,
        isPlaying: true,
        lastReportedTime: 4.6,
        shouldPlay: true
      })
    ).toMatchObject({
      details: {
        bufferAhead: 0.8,
        isLowBuffer: true
      },
      shouldRecord: true
    });
  });

  it("skips inactive, paused, and unknown buffer samples", () => {
    expect(
      getVideoBufferHealthSample({
        bufferedPosition: 8,
        currentTime: 5,
        isPlaying: false,
        lastReportedTime: 0,
        shouldPlay: true
      }).shouldRecord
    ).toBe(false);
    expect(
      getVideoBufferHealthSample({
        bufferedPosition: 8,
        currentTime: 5,
        isPlaying: true,
        lastReportedTime: 0,
        shouldPlay: false
      }).shouldRecord
    ).toBe(false);
    expect(
      getVideoBufferHealthSample({
        bufferedPosition: -1,
        currentTime: 5,
        isPlaying: true,
        lastReportedTime: 0,
        shouldPlay: true
      }).shouldRecord
    ).toBe(false);
  });
});

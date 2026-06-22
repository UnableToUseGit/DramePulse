import { getVideoPlaybackCommand } from "../videoPlayback";

describe("videoPlayback", () => {
  it("blocks play commands while a required seek is still pending", () => {
    expect(
      getVideoPlaybackCommand({
        isStarted: true,
        shouldPlay: true,
        playerIsPlaying: false,
        isPlaybackBlocked: true
      })
    ).toBeUndefined();

    expect(
      getVideoPlaybackCommand({
        isStarted: true,
        shouldPlay: true,
        playerIsPlaying: true,
        isPlaybackBlocked: true
      })
    ).toBe("pause");
  });
});

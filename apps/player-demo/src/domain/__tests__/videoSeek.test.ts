import { getVideoSeekOperation, shouldHoldOptimisticSeekTime } from "../videoSeek";

describe("videoSeek", () => {
  it("uses relative seek for user timeline jumps to avoid frame-accurate HLS seeks", () => {
    expect(
      getVideoSeekOperation({
        playerCurrentTime: 42,
        reason: "user_seek",
        targetTime: 96
      })
    ).toEqual({
      type: "relative",
      delta: 54
    });
  });

  it("keeps exact seek when the current player time is unavailable", () => {
    expect(
      getVideoSeekOperation({
        playerCurrentTime: Number.NaN,
        reason: "user_seek",
        targetTime: 96
      })
    ).toEqual({
      type: "exact",
      targetTime: 96
    });
  });

  it("holds the optimistic timeline time while stale updates are still far from the seek target", () => {
    expect(
      shouldHoldOptimisticSeekTime({
        currentTime: 42,
        targetTime: 96
      })
    ).toBe(true);
  });

  it("releases the optimistic timeline time once playback reaches the seek target", () => {
    expect(
      shouldHoldOptimisticSeekTime({
        currentTime: 95.7,
        targetTime: 96
      })
    ).toBe(false);
  });
});

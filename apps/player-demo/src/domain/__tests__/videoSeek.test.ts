import { getVideoSeekOperation } from "../videoSeek";

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
});

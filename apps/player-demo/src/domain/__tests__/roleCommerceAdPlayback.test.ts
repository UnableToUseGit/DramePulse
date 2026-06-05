import {
  getRoleCommerceAdCompletionAction,
  getRoleCommerceAdProductSheetOpenAction,
  getRoleCommerceAdPlaybackState
} from "../roleCommerceAdPlayback";

describe("roleCommerceAdPlayback", () => {
  it("plays only when the ad page is active and the user intent is playing", () => {
    expect(getRoleCommerceAdPlaybackState({ isActive: true, userPlaybackIntent: "playing" })).toEqual({
      isStarted: true,
      shouldPlay: true,
      shouldShowPauseHint: false
    });
    expect(getRoleCommerceAdPlaybackState({ isActive: true, userPlaybackIntent: "paused" })).toEqual({
      isStarted: true,
      shouldPlay: false,
      shouldShowPauseHint: true
    });
    expect(getRoleCommerceAdPlaybackState({ isActive: false, userPlaybackIntent: "playing" })).toEqual({
      isStarted: true,
      shouldPlay: false,
      shouldShowPauseHint: false
    });
    expect(getRoleCommerceAdPlaybackState({ isActive: false, userPlaybackIntent: "paused" })).toEqual({
      isStarted: true,
      shouldPlay: false,
      shouldShowPauseHint: false
    });
  });

  it("pauses instead of advancing when an ad finishes", () => {
    expect(getRoleCommerceAdCompletionAction()).toEqual({
      nextPlaybackIntent: "paused",
      shouldAutoAdvance: false,
      shouldShowNextItemHint: false
    });
  });

  it("keeps the current playback intent when opening the product sheet", () => {
    expect(getRoleCommerceAdProductSheetOpenAction({ currentPlaybackIntent: "playing" })).toEqual({
      nextPlaybackIntent: "playing",
      shouldShowProductSheet: true
    });
    expect(getRoleCommerceAdProductSheetOpenAction({ currentPlaybackIntent: "paused" })).toEqual({
      nextPlaybackIntent: "paused",
      shouldShowProductSheet: true
    });
  });
});

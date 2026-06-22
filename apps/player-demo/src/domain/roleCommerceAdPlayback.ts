export type RoleCommerceAdPlaybackIntent = "playing" | "paused";

export function getRoleCommerceAdPlaybackState({
  isActive,
  userPlaybackIntent
}: {
  isActive: boolean;
  userPlaybackIntent: RoleCommerceAdPlaybackIntent;
}) {
  return {
    isStarted: true,
    shouldPlay: isActive && userPlaybackIntent === "playing",
    shouldShowPauseHint: isActive && userPlaybackIntent === "paused"
  };
}

export function getRoleCommerceAdCompletionAction() {
  return {
    nextPlaybackIntent: "paused" as const,
    shouldAutoAdvance: false,
    shouldShowNextItemHint: false
  };
}

export function getRoleCommerceAdProductSheetOpenAction({
  currentPlaybackIntent
}: {
  currentPlaybackIntent: RoleCommerceAdPlaybackIntent;
}) {
  return {
    nextPlaybackIntent: currentPlaybackIntent,
    shouldShowProductSheet: true
  };
}

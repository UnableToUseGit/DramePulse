export type VideoSeekReason = "user_seek" | "assistant_seek" | "resume" | string | undefined;

export type VideoSeekOperation =
  | { type: "relative"; delta: number }
  | { type: "exact"; targetTime: number };

const RELATIVE_SEEK_REASONS = new Set<VideoSeekReason>(["user_seek", "assistant_seek"]);
const MIN_RELATIVE_SEEK_DELTA_SEC = 0.05;

export function getVideoSeekOperation({
  playerCurrentTime,
  reason,
  targetTime
}: {
  playerCurrentTime: number;
  reason: VideoSeekReason;
  targetTime: number;
}): VideoSeekOperation {
  if (
    RELATIVE_SEEK_REASONS.has(reason) &&
    Number.isFinite(playerCurrentTime) &&
    Math.abs(targetTime - playerCurrentTime) >= MIN_RELATIVE_SEEK_DELTA_SEC
  ) {
    return {
      type: "relative",
      delta: targetTime - playerCurrentTime
    };
  }
  return {
    type: "exact",
    targetTime
  };
}

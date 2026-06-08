const DEFAULT_TIME_ADVANCE_THRESHOLD_SEC = 0.2;

export type VideoReadinessEvent =
  | { type: "first_frame_render" }
  | { type: "playing_change"; isPlaying: boolean }
  | { type: "time_update"; currentTime: number };

export interface VideoReadinessState {
  initialTime: number;
  hasFirstFrame: boolean;
  isPlaying: boolean;
  hasAdvancedTime: boolean;
  isReady: boolean;
}

export function createVideoReadinessState(initialTime: number): VideoReadinessState {
  return {
    initialTime,
    hasFirstFrame: false,
    isPlaying: false,
    hasAdvancedTime: false,
    isReady: false
  };
}

export function reduceVideoReadinessState(
  state: VideoReadinessState,
  event: VideoReadinessEvent,
  timeAdvanceThresholdSec = DEFAULT_TIME_ADVANCE_THRESHOLD_SEC
): VideoReadinessState {
  const next = { ...state };
  if (event.type === "first_frame_render") {
    next.hasFirstFrame = true;
  }
  if (event.type === "playing_change") {
    next.isPlaying = event.isPlaying;
  }
  if (event.type === "time_update") {
    next.hasAdvancedTime =
      next.hasAdvancedTime || event.currentTime - next.initialTime >= timeAdvanceThresholdSec;
  }
  next.isReady = next.hasFirstFrame && next.isPlaying && next.hasAdvancedTime;
  return next;
}

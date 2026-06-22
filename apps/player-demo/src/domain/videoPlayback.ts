export type VideoPlaybackCommand = "play" | "pause" | undefined;

export function getVideoPlaybackCommand({
  isStarted,
  shouldPlay,
  playerIsPlaying,
  isPlaybackBlocked = false
}: {
  isStarted: boolean;
  shouldPlay: boolean;
  playerIsPlaying: boolean;
  isPlaybackBlocked?: boolean;
}): VideoPlaybackCommand {
  const canPlay = isStarted && shouldPlay && !isPlaybackBlocked;
  if (canPlay === playerIsPlaying) {
    return undefined;
  }
  return canPlay ? "play" : "pause";
}

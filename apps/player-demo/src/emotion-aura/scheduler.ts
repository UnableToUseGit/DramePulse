import type { EmotionAuraCue } from "./types";

export function findActiveEmotionAuraCue({
  cues,
  currentTime,
  completedCueIds
}: {
  cues: EmotionAuraCue[];
  currentTime: number;
  completedCueIds: Set<string>;
}) {
  return cues.find(
    (cue) =>
      !completedCueIds.has(cue.cueId) &&
      currentTime >= cue.triggerTime &&
      currentTime <= cue.triggerTime + cue.durationSec
  );
}

export function getVisibleEmotionAuraCue({
  activeCue,
  engagedCue,
  settledCue
}: {
  activeCue: EmotionAuraCue | undefined;
  engagedCue: EmotionAuraCue | undefined;
  settledCue: EmotionAuraCue | undefined;
}) {
  return settledCue ?? engagedCue ?? activeCue;
}

export function getSettlingEmotionAuraCue({
  activeCue,
  engagedCue
}: {
  activeCue: EmotionAuraCue | undefined;
  engagedCue: EmotionAuraCue | undefined;
}) {
  return engagedCue ?? activeCue;
}

export function shouldTimeoutEmotionAuraCue({ cue, currentTime }: { cue: EmotionAuraCue; currentTime: number }) {
  return currentTime > cue.triggerTime + cue.durationSec;
}

export function shouldResetEmotionAuraCue({
  cue,
  previousTime,
  currentTime
}: {
  cue: EmotionAuraCue;
  previousTime: number;
  currentTime: number;
}) {
  return previousTime >= cue.triggerTime && currentTime < cue.triggerTime;
}

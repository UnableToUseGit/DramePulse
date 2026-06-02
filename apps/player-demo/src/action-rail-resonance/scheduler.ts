import type { ActionRailResonanceCue } from "./types";

export function getActiveActionRailResonanceCue({
  cues,
  currentTime,
  completedCueIds
}: {
  cues: ActionRailResonanceCue[];
  currentTime: number;
  completedCueIds: Set<string>;
}) {
  return cues.find((cue) => {
    const startsAt = cue.triggerTime;
    const endsAt = cue.triggerTime + cue.durationSec;
    return !completedCueIds.has(cue.cueId) && currentTime >= startsAt && currentTime <= endsAt;
  });
}

export function shouldResetActionRailResonanceCue({
  previousTime,
  currentTime,
  firstTriggerTime
}: {
  previousTime: number;
  currentTime: number;
  firstTriggerTime: number;
}) {
  return previousTime >= firstTriggerTime && currentTime < firstTriggerTime;
}

export function getVisibleActionRailResonanceCue({
  activeCue,
  participatingCue
}: {
  activeCue: ActionRailResonanceCue | undefined;
  participatingCue: ActionRailResonanceCue | undefined;
}) {
  return participatingCue ?? activeCue;
}

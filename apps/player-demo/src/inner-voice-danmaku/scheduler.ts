import type { InnerVoiceDanmakuCue } from "./types";

export function getActiveInnerVoiceCue({
  cues,
  currentTime,
  completedCueIds
}: {
  cues: InnerVoiceDanmakuCue[];
  currentTime: number;
  completedCueIds: Set<string>;
}) {
  return cues.find((cue) => {
    const startsAt = cue.triggerTime;
    const endsAt = cue.triggerTime + cue.durationSec;
    return !completedCueIds.has(cue.cueId) && currentTime >= startsAt && currentTime <= endsAt;
  });
}

export function shouldResetInnerVoiceCue({
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

export function getVisibleInnerVoiceCue({
  activeCue,
  launchingCue
}: {
  activeCue: InnerVoiceDanmakuCue | undefined;
  launchingCue: InnerVoiceDanmakuCue | undefined;
}) {
  return launchingCue ?? activeCue;
}

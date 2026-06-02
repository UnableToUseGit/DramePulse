import type { InteractionExample, InteractionPresentationType } from "./types";

const LABELS: Record<InteractionPresentationType, string> = {
  none: "Off",
  poll_bar: "Poll Bar",
  danmaku_poll: "Danmaku Poll",
  emoji_hold: "Emoji Hold",
  emotion_aura: "Emotion Aura",
  inner_voice_danmaku: "Inner Voice"
};

export function getPresentationLabel(type: InteractionPresentationType) {
  return LABELS[type];
}

export function shouldShowExample({
  example,
  currentTime,
  isStarted,
  dismissed,
  presentationType
}: {
  example: InteractionExample;
  currentTime: number;
  isStarted: boolean;
  dismissed: boolean;
  presentationType: InteractionPresentationType;
}) {
  return presentationType !== "none" && isStarted && !dismissed && currentTime >= example.triggerTimeSec;
}

export function shouldResetExample({
  previousTime,
  currentTime,
  triggerTimeSec
}: {
  previousTime: number;
  currentTime: number;
  triggerTimeSec: number;
}) {
  return previousTime >= triggerTimeSec && currentTime < triggerTimeSec;
}

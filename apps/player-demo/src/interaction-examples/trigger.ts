import type { InteractionExample, InteractionPresentationType } from "./types";

const LABELS: Record<InteractionPresentationType, string> = {
  none: "Off",
  danmaku_poll: "Danmaku Poll",
  inner_voice_danmaku: "Inner Voice",
  action_rail_thrill: "Rail 爽点",
  action_rail_candy: "Rail 撒糖",
  action_rail_laugh: "Rail 大笑",
  action_rail_tear: "Rail 泪目"
};

export function getPresentationLabel(type: InteractionPresentationType) {
  return LABELS[type];
}

export function isActionRailResonancePresentation(type: InteractionPresentationType) {
  return (
    type === "action_rail_thrill" ||
    type === "action_rail_candy" ||
    type === "action_rail_laugh" ||
    type === "action_rail_tear"
  );
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
  void example;
  void currentTime;
  return presentationType !== "none" && isStarted && !dismissed;
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

export type InteractionPresentationType =
  | "none"
  | "poll_bar"
  | "danmaku_poll"
  | "emoji_hold"
  | "emotion_aura"
  | "inner_voice_danmaku"
  | "action_rail_resonance";

export type InteractionReaction = {
  id: string;
  emoji: string;
  label: string;
};

export type InteractionExample = {
  id: string;
  label: string;
  triggerTimeSec: number;
  prompt: string;
  reactions: InteractionReaction[];
};

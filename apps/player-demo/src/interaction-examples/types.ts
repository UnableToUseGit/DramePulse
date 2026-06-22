export type InteractionPresentationType =
  | "none"
  | "danmaku_poll"
  | "inner_voice_danmaku"
  | "action_rail_thrill"
  | "action_rail_candy"
  | "action_rail_laugh"
  | "action_rail_tear";

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

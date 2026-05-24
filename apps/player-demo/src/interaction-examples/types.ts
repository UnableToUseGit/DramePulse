export type InteractionPresentationType = "none" | "poll_bar" | "emoji_hold";

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

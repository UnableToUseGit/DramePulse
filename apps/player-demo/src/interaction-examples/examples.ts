import type { InteractionExample } from "./types";

export const DEFAULT_INTERACTION_EXAMPLE: InteractionExample = {
  id: "fixed-emotion-moment",
  label: "固定情绪触发点",
  triggerTimeSec: 2,
  prompt: "这一刻你什么感觉？",
  reactions: [
    { id: "fire", emoji: "🔥", label: "爽" },
    { id: "sad", emoji: "😭", label: "心疼" },
    { id: "hooked", emoji: "😍", label: "上头" }
  ]
};

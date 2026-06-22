import type { Ionicons } from "@expo/vector-icons";

export type ActionRailResonanceEmotionType = "爽点" | "笑点" | "甜点" | "泪点";

export type ActionRailResonanceCue = {
  cueId: string;
  videoId: string;
  highlightId: string;
  triggerTime: number;
  durationSec: number;
  emotionType: ActionRailResonanceEmotionType;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  baseCount: number;
  feedbackText: string;
};

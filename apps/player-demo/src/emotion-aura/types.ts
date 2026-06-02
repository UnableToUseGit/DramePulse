export type EmotionAuraType = "爽点" | "笑点" | "甜点" | "泪点";

export type EmotionEnergyLevel = "low" | "medium" | "high";

export type EmotionAuraCue = {
  cueId: string;
  videoId: string;
  highlightId: string;
  triggerTime: number;
  durationSec: number;
  emotionType: EmotionAuraType;
  label: string;
  resonanceText: string;
};

import type { EmotionAuraCue } from "./types";

export const EMOTION_AURA_CUES: EmotionAuraCue[] = [
  {
    cueId: "aura_demo_fire",
    videoId: "demo",
    highlightId: "h_aura_fire",
    triggerTime: 2,
    durationSec: 6,
    emotionType: "爽点",
    label: "爽到了",
    resonanceText: "你和 2.4 万人一起爽到了"
  },
  {
    cueId: "aura_demo_laugh",
    videoId: "demo",
    highlightId: "h_aura_laugh",
    triggerTime: 10,
    durationSec: 6,
    emotionType: "笑点",
    label: "绷不住了",
    resonanceText: "你和 1.8 万人一起笑出了声"
  },
  {
    cueId: "aura_demo_sweet",
    videoId: "demo",
    highlightId: "h_aura_sweet",
    triggerTime: 18,
    durationSec: 6,
    emotionType: "甜点",
    label: "磕到了",
    resonanceText: "你和 3.1 万人一起磕到了"
  },
  {
    cueId: "aura_demo_tear",
    videoId: "demo",
    highlightId: "h_aura_tear",
    triggerTime: 26,
    durationSec: 6,
    emotionType: "泪点",
    label: "破防了",
    resonanceText: "你和 1.2 万人一起破防了"
  }
];

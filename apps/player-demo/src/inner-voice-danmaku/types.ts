export type InnerVoiceDanmakuCue = {
  cueId: string;
  videoId: string;
  highlightId: string;
  triggerTime: number;
  durationSec: number;
  text: string;
  danmakuTrack?: number;
};

export type SentInnerVoiceDanmaku = {
  id: string;
  text: string;
  timeSec: number;
  sentAtMs: number;
};

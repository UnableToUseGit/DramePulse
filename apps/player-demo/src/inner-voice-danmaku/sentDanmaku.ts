import type { DanmakuItem } from "../domain/types";
import type { InnerVoiceDanmakuCue, SentInnerVoiceDanmaku } from "./types";

export function createSentInnerVoiceDanmaku({
  cueId,
  text,
  currentTime,
  nowMs = Date.now()
}: {
  cueId: string;
  text: string;
  currentTime: number;
  nowMs?: number;
}): SentInnerVoiceDanmaku {
  return {
    id: `${cueId}-${nowMs}`,
    text,
    timeSec: currentTime,
    sentAtMs: nowMs
  };
}

export function createSentInnerVoiceDanmakuFromCue({
  cue,
  currentTime,
  nowMs
}: {
  cue: InnerVoiceDanmakuCue;
  currentTime: number;
  nowMs?: number;
}) {
  return createSentInnerVoiceDanmaku({
    cueId: cue.cueId,
    text: cue.text,
    currentTime,
    nowMs
  });
}

export function toDanmakuItems(items: SentInnerVoiceDanmaku[]): DanmakuItem[] {
  return items.map((item) => ({
    danmaku_id: item.id,
    time_sec: item.timeSec,
    text: item.text
  }));
}

import type { DanmakuItem } from "./types";

export interface DanmakuSamplingOptions {
  bucketSec: number;
  minIntervalSec: number;
  maxTextLength: number;
}

const DEFAULT_OPTIONS: DanmakuSamplingOptions = {
  bucketSec: 1,
  minIntervalSec: 1,
  maxTextLength: 16
};

export function sampleMobileDanmaku(
  items: DanmakuItem[],
  options: Partial<DanmakuSamplingOptions> = {}
): DanmakuItem[] {
  const resolvedOptions = { ...DEFAULT_OPTIONS, ...options };
  const buckets = new Map<number, DanmakuItem[]>();

  for (const item of items) {
    if (item.text.length > resolvedOptions.maxTextLength) {
      continue;
    }

    const bucket = Math.floor(item.time_sec / resolvedOptions.bucketSec);
    const bucketItems = buckets.get(bucket) ?? [];
    bucketItems.push(item);
    buckets.set(bucket, bucketItems);
  }

  const bucketWinners = [...buckets.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, bucketItems]) => bucketItems.sort(compareDanmakuQuality)[0]);

  const sampled: DanmakuItem[] = [];
  let lastAcceptedTime = -Infinity;
  for (const item of bucketWinners) {
    if (item.time_sec - lastAcceptedTime <= resolvedOptions.minIntervalSec) {
      continue;
    }
    sampled.push(item);
    lastAcceptedTime = item.time_sec;
  }

  return sampled.sort((a, b) => a.time_sec - b.time_sec);
}

function compareDanmakuQuality(a: DanmakuItem, b: DanmakuItem): number {
  const scoreA = getQualityScore(a);
  const scoreB = getQualityScore(b);
  if (scoreA !== scoreB) {
    return scoreB - scoreA;
  }
  if (a.text.length !== b.text.length) {
    return a.text.length - b.text.length;
  }
  return a.time_sec - b.time_sec;
}

function getQualityScore(item: DanmakuItem): number {
  return (item.digg_count ?? 0) * 2 + (item.score ?? 0);
}

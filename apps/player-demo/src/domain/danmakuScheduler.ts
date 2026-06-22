import type { DanmakuItem } from "./types";

export interface PendingDanmakuItem {
  id: string;
  text: string;
  timeSec: number;
  variant?: DanmakuItem["variant"];
}

export interface RunningDanmakuItem extends PendingDanmakuItem {
  laneIndex: number;
  width: number;
  height: number;
  utcStartSec: number;
}

export interface PositionedDanmakuItem extends RunningDanmakuItem {
  x: number;
}

export function getDanmakuId(item: DanmakuItem): string;
export function getDanmakuId(item: PendingDanmakuItem): string;
export function getDanmakuId(item: DanmakuItem | PendingDanmakuItem): string {
  if ("id" in item) {
    return item.id;
  }
  return String(item.danmaku_id ?? `${item.time_sec}-${item.text}`);
}

export function calculateDanmakuDuration({
  stageWidth,
  speed
}: {
  stageWidth: number;
  speed: number;
}): number {
  if (stageWidth <= 0 || speed <= 0) {
    return 4;
  }
  return stageWidth / speed;
}

export function calculateDanmakuPlaybackDelta({
  deltaSec,
  playbackRate
}: {
  deltaSec: number;
  playbackRate: number;
}): number {
  if (!Number.isFinite(playbackRate) || playbackRate <= 0) {
    return deltaSec;
  }
  return deltaSec * playbackRate;
}

export function findStartPositionAfterSeek(danmaku: DanmakuItem[], seekTime: number): number {
  let left = 0;
  let right = danmaku.length;

  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    if (danmaku[mid].time_sec < seekTime) {
      left = mid + 1;
    } else {
      right = mid;
    }
  }

  return left;
}

export function getNextPositionAfterDanmakuUpdate({
  previousDanmaku,
  nextDanmaku,
  previousPosition
}: {
  previousDanmaku: DanmakuItem[];
  nextDanmaku: DanmakuItem[];
  previousPosition: number;
  currentTime?: number;
}): number {
  const previousScannedItems = previousDanmaku.slice(0, previousPosition);
  let nextPosition = 0;

  for (const item of previousScannedItems) {
    const nextIndex = nextDanmaku.findIndex((nextItem) => getDanmakuId(nextItem) === getDanmakuId(item));
    if (nextIndex >= nextPosition) {
      nextPosition = nextIndex + 1;
    }
  }

  return nextPosition;
}

export function getPendingDanmaku({
  danmaku,
  position,
  currentTime,
  durationSec,
  maxPending
}: {
  danmaku: DanmakuItem[];
  position: number;
  currentTime: number;
  durationSec: number;
  maxPending: number;
}): { items: PendingDanmakuItem[]; nextPosition: number } {
  const items: PendingDanmakuItem[] = [];
  let nextPosition = position;

  while (nextPosition < danmaku.length && items.length < maxPending) {
    const item = danmaku[nextPosition];
    if (item.time_sec > currentTime) {
      break;
    }

    if (currentTime - item.time_sec <= durationSec) {
      items.push({
        id: getDanmakuId(item),
        text: item.text,
        timeSec: item.time_sec,
        ...(item.variant ? { variant: item.variant } : {})
      });
    }
    nextPosition += 1;
  }

  return { items, nextPosition };
}

export function advanceRunningDanmaku({
  running,
  clockSec,
  stageWidth,
  durationSec
}: {
  running: RunningDanmakuItem[];
  clockSec: number;
  stageWidth: number;
  durationSec: number;
}): PositionedDanmakuItem[] {
  return running
    .map((item) => {
      const totalDistance = stageWidth + item.width;
      const elapsed = Math.max(0, clockSec - item.utcStartSec);
      const x = stageWidth - (totalDistance * elapsed) / durationSec;
      return { ...item, x };
    })
    .filter((item) => item.x + item.width >= 0);
}

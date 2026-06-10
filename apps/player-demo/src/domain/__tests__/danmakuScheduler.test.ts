import {
  advanceRunningDanmaku,
  calculateDanmakuDuration,
  calculateDanmakuPlaybackDelta,
  findStartPositionAfterSeek,
  getDanmakuId,
  getNextPositionAfterDanmakuUpdate,
  getPendingDanmaku
} from "../danmakuScheduler";
import type { DanmakuItem } from "../types";

const danmaku: DanmakuItem[] = [
  { danmaku_id: "a", time_sec: 1.1, text: "第一条" },
  { danmaku_id: "b", time_sec: 1.4, text: "同一秒的第二条" },
  { danmaku_id: "c", time_sec: 2.2, text: "下一秒" },
  { danmaku_id: "d", time_sec: 9.2, text: "很久以后" }
];

describe("danmakuScheduler", () => {
  it("calculates shared duration from stage width and speed", () => {
    expect(calculateDanmakuDuration({ stageWidth: 360, speed: 90 })).toBe(4);
  });

  it("scales danmaku clock delta by playback rate", () => {
    expect(calculateDanmakuPlaybackDelta({ deltaSec: 0.5, playbackRate: 2 })).toBe(1);
    expect(calculateDanmakuPlaybackDelta({ deltaSec: 0.5, playbackRate: 0.75 })).toBe(0.375);
  });

  it("falls back to realtime danmaku clock delta for invalid playback rates", () => {
    expect(calculateDanmakuPlaybackDelta({ deltaSec: 0.5, playbackRate: 0 })).toBe(0.5);
    expect(calculateDanmakuPlaybackDelta({ deltaSec: 0.5, playbackRate: Number.NaN })).toBe(0.5);
  });

  it("finds the first danmaku at or after seek time", () => {
    expect(findStartPositionAfterSeek(danmaku, 0)).toBe(0);
    expect(findStartPositionAfterSeek(danmaku, 1.4)).toBe(1);
    expect(findStartPositionAfterSeek(danmaku, 2.5)).toBe(3);
  });

  it("returns pending danmaku since the current position and skips stale items", () => {
    const result = getPendingDanmaku({
      danmaku,
      position: 0,
      currentTime: 2.4,
      durationSec: 4,
      maxPending: 10
    });

    expect(result.nextPosition).toBe(3);
    expect(result.items.map(getDanmakuId)).toEqual(["a", "b", "c"]);

    const stale = getPendingDanmaku({
      danmaku,
      position: 0,
      currentTime: 8,
      durationSec: 4,
      maxPending: 10
    });

    expect(stale.nextPosition).toBe(3);
    expect(stale.items).toEqual([]);
  });

  it("preserves danmaku variants when moving items into the pending queue", () => {
    const result = getPendingDanmaku({
      danmaku: [{ danmaku_id: "voice", time_sec: 1.1, text: "这是我的心里话", variant: "inner_voice" }],
      position: 0,
      currentTime: 1.2,
      durationSec: 4,
      maxPending: 10
    });

    expect(result.items).toEqual([
      {
        id: "voice",
        text: "这是我的心里话",
        timeSec: 1.1,
        variant: "inner_voice"
      }
    ]);
  });

  it("moves running danmaku by measured width and only removes it after it fully leaves screen", () => {
    const running = [
      {
        id: "a",
        text: "第一条",
        timeSec: 1,
        laneIndex: 0,
        width: 120,
        height: 28,
        utcStartSec: 10
      }
    ];

    const halfWay = advanceRunningDanmaku({
      running,
      clockSec: 12,
      stageWidth: 360,
      durationSec: 4
    });

    expect(halfWay).toEqual([
      {
        ...running[0],
        x: 120
      }
    ]);

    const justAtLeftEdge = advanceRunningDanmaku({
      running,
      clockSec: 14,
      stageWidth: 360,
      durationSec: 4
    });
    expect(justAtLeftEdge).toEqual([{ ...running[0], x: -120 }]);

    const offscreen = advanceRunningDanmaku({
      running,
      clockSec: 14.1,
      stageWidth: 360,
      durationSec: 4
    });
    expect(offscreen).toEqual([]);
  });

  it("keeps the current scan position when new danmaku is appended after the scanned range", () => {
    const nextDanmaku = [...danmaku, { danmaku_id: "new", time_sec: 5, text: "新发送" }];

    expect(
      getNextPositionAfterDanmakuUpdate({
        previousDanmaku: danmaku,
        nextDanmaku,
        previousPosition: 3
      })
    ).toBe(3);
  });

  it("does not skip just-passed items when danmaku first loads during playback", () => {
    expect(
      getNextPositionAfterDanmakuUpdate({
        previousDanmaku: [],
        nextDanmaku: danmaku,
        previousPosition: 0,
        currentTime: 2
      })
    ).toBe(0);
  });

  it("repositions the scan when new danmaku is inserted before the scanned range", () => {
    const nextDanmaku = [{ danmaku_id: "new", time_sec: 1.5, text: "插入" }, ...danmaku].sort(
      (a, b) => a.time_sec - b.time_sec
    );

    expect(
      getNextPositionAfterDanmakuUpdate({
        previousDanmaku: danmaku,
        nextDanmaku,
        previousPosition: 3
      })
    ).toBe(4);
  });
});

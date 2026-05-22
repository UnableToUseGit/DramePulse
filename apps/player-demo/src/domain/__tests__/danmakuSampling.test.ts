import { sampleMobileDanmaku } from "../danmakuSampling";
import type { DanmakuItem } from "../types";

const items: DanmakuItem[] = [
  { danmaku_id: "low", time_sec: 1.1, text: "低质量", digg_count: 1, score: 1 },
  { danmaku_id: "high", time_sec: 1.4, text: "高赞短弹幕", digg_count: 80, score: 10 },
  { danmaku_id: "long", time_sec: 2.1, text: "这是一条非常非常非常非常长的弹幕", digg_count: 100, score: 100 },
  { danmaku_id: "next", time_sec: 2.4, text: "下一条", digg_count: 20, score: 20 },
  { danmaku_id: "later", time_sec: 3.2, text: "稍后出现", digg_count: 10, score: 10 }
];

describe("sampleMobileDanmaku", () => {
  it("keeps at most one best short item in each time bucket", () => {
    const sampled = sampleMobileDanmaku(items, {
      bucketSec: 1,
      minIntervalSec: 0,
      maxTextLength: 12
    });

    expect(sampled.map((item) => item.danmaku_id)).toEqual(["high", "next", "later"]);
  });

  it("applies a global minimum interval for mobile density", () => {
    const sampled = sampleMobileDanmaku(items, {
      bucketSec: 1,
      minIntervalSec: 1,
      maxTextLength: 12
    });

    expect(sampled.map((item) => item.danmaku_id)).toEqual(["high", "later"]);
  });
});

import type { DanmakuItem } from "../domain/types";

export type DanmakuLoadState = "loading" | "ready" | "error";

export function useDanmakuFeed(danmakuUrl: string, enabled = true) {
  void danmakuUrl;
  void enabled;
  return { danmaku: [] as DanmakuItem[], danmakuState: "ready" as DanmakuLoadState };
}

import { useEffect, useState } from "react";
import { loadVideoDanmaku } from "../domain/playerApi";
import type { DanmakuItem } from "../domain/types";

export type DanmakuLoadState = "loading" | "ready" | "error";

export function useDanmakuFeed(danmakuUrl: string) {
  const [danmaku, setDanmaku] = useState<DanmakuItem[]>([]);
  const [danmakuState, setDanmakuState] = useState<DanmakuLoadState>("loading");

  useEffect(() => {
    let cancelled = false;
    setDanmakuState("loading");
    setDanmaku([]);
    loadVideoDanmaku({ danmakuUrl })
      .then((items) => {
        if (!cancelled) {
          setDanmaku(items);
          setDanmakuState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDanmaku([]);
          setDanmakuState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [danmakuUrl]);

  return { danmaku, danmakuState };
}

import { useEffect, useMemo, useRef, useState } from "react";
import { normalizeDanmakuResponse } from "../domain/playerApi";
import type { DanmakuItem } from "../domain/types";

export type DanmakuLoadState = "loading" | "ready" | "error";

const DANMAKU_FETCH_LIMIT = 300;

export function buildDanmakuFetchUrl(danmakuUrl: string) {
  const separator = danmakuUrl.includes("?") ? "&" : "?";
  return `${danmakuUrl}${separator}limit=${DANMAKU_FETCH_LIMIT}`;
}

function getDanmakuKey(item: DanmakuItem) {
  return item.danmaku_id ?? `${item.time_sec}:${item.text}`;
}

function mergeDanmakuItems(previous: DanmakuItem[], next: DanmakuItem[]) {
  const itemsByKey = new Map(previous.map((item) => [getDanmakuKey(item), item]));
  next.forEach((item) => {
    itemsByKey.set(getDanmakuKey(item), item);
  });
  return Array.from(itemsByKey.values()).sort((a, b) => a.time_sec - b.time_sec);
}

export function useDanmakuFeed(danmakuUrl: string, enabled = true, _currentTime = 0) {
  const [danmaku, setDanmaku] = useState<DanmakuItem[]>([]);
  const [danmakuState, setDanmakuState] = useState<DanmakuLoadState>("ready");
  const hasFetchedRef = useRef(false);
  const isInFlightRef = useRef(false);
  const requestUrl = useMemo(() => (danmakuUrl ? buildDanmakuFetchUrl(danmakuUrl) : ""), [danmakuUrl]);

  useEffect(() => {
    setDanmaku([]);
    setDanmakuState("ready");
    hasFetchedRef.current = false;
    isInFlightRef.current = false;
  }, [danmakuUrl]);

  useEffect(() => {
    if (!enabled || !requestUrl || hasFetchedRef.current || isInFlightRef.current) {
      return;
    }

    const abortController = new AbortController();
    isInFlightRef.current = true;
    setDanmakuState("loading");

    fetch(requestUrl, { signal: abortController.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Request failed ${response.status}: ${danmakuUrl}`);
        }
        return response.json();
      })
      .then((payload) => {
        const nextItems = normalizeDanmakuResponse(payload);
        hasFetchedRef.current = true;
        setDanmaku((items) => mergeDanmakuItems(items, nextItems));
        setDanmakuState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        setDanmakuState("error");
      })
      .finally(() => {
        isInFlightRef.current = false;
      });

    return () => {
      abortController.abort();
    };
  }, [danmakuUrl, enabled, requestUrl]);

  return { danmaku, danmakuState };
}

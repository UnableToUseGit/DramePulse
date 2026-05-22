import { memo, useEffect, useMemo, useRef, useState } from "react";
import { LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import {
  advanceRunningDanmaku,
  calculateDanmakuDuration,
  findStartPositionAfterSeek,
  getPendingDanmaku,
  PendingDanmakuItem,
  PositionedDanmakuItem,
  RunningDanmakuItem
} from "../domain/danmakuScheduler";
import type { DanmakuItem } from "../domain/types";

const LANES = [96, 138, 180];
const SPEED_PX_PER_SEC = 58;
const MAX_PENDING_PER_TICK = 2;
const ESTIMATED_TEXT_WIDTH = 180;
const ESTIMATED_TEXT_HEIGHT = 28;

export function DanmakuLayer({
  currentTime,
  danmaku,
  isPlaying,
  seekVersion
}: {
  currentTime: number;
  danmaku: DanmakuItem[];
  isPlaying: boolean;
  seekVersion: number;
}) {
  const [stageWidth, setStageWidth] = useState(0);
  const [positionedItems, setPositionedItems] = useState<PositionedDanmakuItem[]>([]);
  const currentTimeRef = useRef(currentTime);
  const clockSecRef = useRef(currentTime);
  const positionRef = useRef(0);
  const runningItemsRef = useRef<RunningDanmakuItem[]>([]);
  const frameRef = useRef<number | undefined>(undefined);
  const lastFrameMs = useRef<number | undefined>(undefined);
  const measuredSizeRef = useRef<Map<string, { width: number; height: number }>>(new Map());
  const nextLaneRef = useRef(0);

  const durationSec = useMemo(
    () => calculateDanmakuDuration({ stageWidth, speed: SPEED_PX_PER_SEC }),
    [stageWidth]
  );

  useEffect(() => {
    currentTimeRef.current = currentTime;
    if (!isPlaying) {
      clockSecRef.current = currentTime;
    }
  }, [currentTime, isPlaying]);

  useEffect(() => {
    positionRef.current = findStartPositionAfterSeek(danmaku, currentTime);
    clockSecRef.current = currentTime;
    currentTimeRef.current = currentTime;
    nextLaneRef.current = 0;
    runningItemsRef.current = [];
    setPositionedItems([]);
  }, [danmaku, seekVersion]);

  useEffect(() => {
    if (!isPlaying || stageWidth <= 0) {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
      lastFrameMs.current = undefined;
      return;
    }

    clockSecRef.current = currentTimeRef.current;

    const tick = (frameMs: number) => {
      const previousFrameMs = lastFrameMs.current ?? frameMs;
      const deltaSec = Math.max(0, (frameMs - previousFrameMs) / 1000);
      lastFrameMs.current = frameMs;
      clockSecRef.current += deltaSec;
      const clockSec = clockSecRef.current;
      const pending = getPendingDanmaku({
        danmaku,
        position: positionRef.current,
        currentTime: currentTimeRef.current,
        durationSec,
        maxPending: MAX_PENDING_PER_TICK
      });
      positionRef.current = pending.nextPosition;

      const stillRunning = advanceRunningDanmaku({
        running: runningItemsRef.current,
        clockSec,
        stageWidth,
        durationSec
      });
      const nextItems = pending.items.map((item) => createRunningItem(item, clockSec, nextLaneRef, measuredSizeRef));
      const nextRunning = [...stillRunning, ...nextItems];
      const nextPositioned = advanceRunningDanmaku({
        running: nextRunning,
        clockSec,
        stageWidth,
        durationSec
      });
      runningItemsRef.current = nextRunning;
      setPositionedItems(nextPositioned);

      frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current !== undefined) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
      lastFrameMs.current = undefined;
    };
  }, [danmaku, durationSec, isPlaying, stageWidth]);

  const handleLayout = (event: LayoutChangeEvent) => {
    setStageWidth(event.nativeEvent.layout.width);
  };

  const handleItemLayout = (id: string, event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    if (width <= 0 || height <= 0) {
      return;
    }
    measuredSizeRef.current.set(id, { width, height });
    const nextRunning = runningItemsRef.current.map((item) => (item.id === id ? { ...item, width, height } : item));
    runningItemsRef.current = nextRunning;
  };

  return (
    <View pointerEvents="none" style={styles.root} onLayout={handleLayout}>
      {positionedItems.map((item) => (
        <DanmakuText key={item.id} item={item} onLayout={handleItemLayout} />
      ))}
    </View>
  );
}

function createRunningItem(
  item: PendingDanmakuItem,
  clockSec: number,
  nextLaneRef: React.MutableRefObject<number>,
  measuredSizeRef: React.MutableRefObject<Map<string, { width: number; height: number }>>
): RunningDanmakuItem {
  const measuredSize = measuredSizeRef.current.get(item.id);
  const laneIndex = nextLaneRef.current % LANES.length;
  nextLaneRef.current += 1;

  return {
    ...item,
    laneIndex,
    width: measuredSize?.width ?? ESTIMATED_TEXT_WIDTH,
    height: measuredSize?.height ?? ESTIMATED_TEXT_HEIGHT,
    utcStartSec: clockSec
  };
}

const DanmakuText = memo(function DanmakuText({
  item,
  onLayout
}: {
  item: PositionedDanmakuItem;
  onLayout: (id: string, event: LayoutChangeEvent) => void;
}) {
  return (
    <View
      onLayout={(event) => onLayout(item.id, event)}
      style={[styles.item, { top: LANES[item.laneIndex], transform: [{ translateX: item.x }] }]}
    >
      <Text numberOfLines={1} style={styles.text}>
        {item.text}
      </Text>
    </View>
  );
});

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  },
  item: {
    position: "absolute",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "rgba(0,0,0,0.18)"
  },
  text: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.74)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4
  }
});

import * as Haptics from "expo-haptics";
import { useEffect, useRef, useState } from "react";
import { Image, LayoutChangeEvent, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import {
  ChapterTitleRailItem,
  getChapterTitleRailItems,
  getChapterTicks,
  getSnappedTimelineTime,
  getStoryboardCell,
  getStoryChapterAtTime,
  getTimelinePresentation,
  getTimelineTimeFromPageX,
  StoryboardManifest,
  StoryChapter
} from "../domain/storyNavigation";
import { colors, radii, spacing } from "../theme";

const DRAG_ACTIVATION_DISTANCE_PX = 6;
const CHAPTER_SNAP_THRESHOLD_SECONDS = 1.2;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function PlayerControls({
  currentTime,
  duration,
  hasNextEpisode,
  nextEpisodeLabel,
  onSeekCommit,
  onDragStateChange,
  storyChapters,
  storyboard
}: {
  currentTime: number;
  duration: number;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  onSeekCommit: (time: number) => void;
  onDragStateChange?: (isDragging: boolean) => void;
  storyChapters?: StoryChapter[];
  storyboard?: StoryboardManifest;
}) {
  const safeDuration = duration > 0 ? duration : 1;
  const viewport = useWindowDimensions();
  const [dragTime, setDragTime] = useState<number | undefined>(undefined);
  const [trackWidth, setTrackWidth] = useState(0);
  const [trackPageX, setTrackPageX] = useState(0);
  const onSeekCommitRef = useRef(onSeekCommit);
  const trackTapTargetRef = useRef<View>(null);
  const dragStartXRef = useRef(0);
  const didActivateDragRef = useRef(false);
  const isDragging = dragTime !== undefined;
  const visibleTime = dragTime ?? currentTime;
  const progressRatio = clamp(visibleTime / safeDuration, 0, 1);
  const remainingSeconds = Math.ceil(duration - currentTime);
  const shouldShowNextEpisodeHint = hasNextEpisode && !isDragging && remainingSeconds >= 1 && remainingSeconds <= 3;
  const chapterTicks = getChapterTicks(storyChapters, safeDuration);
  const dragChapter = isDragging ? getStoryChapterAtTime(storyChapters, visibleTime) : undefined;
  const storyboardCell = isDragging ? getStoryboardCell(storyboard, visibleTime) : undefined;
  const timelinePresentation = getTimelinePresentation(isDragging);
  const chapterTitleRailItems = isDragging ? getChapterTitleRailItems(storyChapters, visibleTime) : [];
  const lastHapticBoundaryRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    onSeekCommitRef.current = onSeekCommit;
  }, [onSeekCommit]);

  useEffect(() => {
    onDragStateChange?.(isDragging);
  }, [isDragging, onDragStateChange]);

  const getTimeFromPageX = (pageX: number) => {
    if (trackWidth <= 0) {
      return visibleTime;
    }
    const rawTime = getTimelineTimeFromPageX({
      pageX,
      trackPageX,
      trackWidth,
      duration: safeDuration
    });
    const snapped = getSnappedTimelineTime({
      time: rawTime,
      chapters: storyChapters,
      snapThresholdSeconds: CHAPTER_SNAP_THRESHOLD_SECONDS
    });
    if (snapped.boundaryId && lastHapticBoundaryRef.current !== snapped.boundaryId) {
      lastHapticBoundaryRef.current = snapped.boundaryId;
      Haptics.selectionAsync().catch(() => undefined);
    }
    if (!snapped.boundaryId) {
      lastHapticBoundaryRef.current = undefined;
    }
    return snapped.time;
  };

  const measureTrackPosition = () => {
    trackTapTargetRef.current?.measureInWindow((x) => {
      setTrackPageX(x);
    });
  };

  const handleTrackLayout = (event: LayoutChangeEvent) => {
    setTrackWidth(event.nativeEvent.layout.width);
    measureTrackPosition();
  };

  return (
    <View style={styles.root}>
      {isDragging ? (
        <View pointerEvents="none" style={styles.dragPreview}>
          {storyboardCell ? <StoryboardPreview cell={storyboardCell} /> : null}
          <ChapterTitleRail items={chapterTitleRailItems} fallbackTitle={dragChapter?.title} />
          <Text style={styles.timeLabel}>
            {formatTime(visibleTime)} <Text style={styles.timeTotal}>/ {formatTime(safeDuration)}</Text>
          </Text>
        </View>
      ) : null}
      {isDragging ? (
        <View
          style={[styles.fullscreenScrubLayer, { height: viewport.height }]}
          onStartShouldSetResponder={() => true}
          onMoveShouldSetResponder={() => true}
          onResponderMove={(event) => {
            setDragTime(getTimeFromPageX(event.nativeEvent.pageX));
          }}
          onResponderRelease={(event) => {
            onSeekCommitRef.current(getTimeFromPageX(event.nativeEvent.pageX));
            didActivateDragRef.current = false;
            lastHapticBoundaryRef.current = undefined;
            setDragTime(undefined);
          }}
          onResponderTerminate={() => {
            didActivateDragRef.current = false;
            lastHapticBoundaryRef.current = undefined;
            setDragTime(undefined);
          }}
        />
      ) : null}
      <View style={styles.progressRow}>
        <View
          ref={trackTapTargetRef}
          style={styles.trackTapTarget}
          onLayout={handleTrackLayout}
          onStartShouldSetResponder={() => true}
          onMoveShouldSetResponder={() => true}
          onResponderTerminationRequest={() => false}
          onResponderGrant={(event) => {
            measureTrackPosition();
            dragStartXRef.current = event.nativeEvent.pageX;
            didActivateDragRef.current = false;
          }}
          onResponderMove={(event) => {
            const deltaX = event.nativeEvent.pageX - dragStartXRef.current;
            if (!didActivateDragRef.current && Math.abs(deltaX) < DRAG_ACTIVATION_DISTANCE_PX) {
              return;
            }
            didActivateDragRef.current = true;
            setDragTime(getTimeFromPageX(event.nativeEvent.pageX));
          }}
          onResponderRelease={(event) => {
            if (didActivateDragRef.current) {
              const nextTime = getTimeFromPageX(event.nativeEvent.pageX);
              onSeekCommitRef.current(nextTime);
            }
            didActivateDragRef.current = false;
            lastHapticBoundaryRef.current = undefined;
            setDragTime(undefined);
          }}
          onResponderTerminate={() => {
            didActivateDragRef.current = false;
            lastHapticBoundaryRef.current = undefined;
            setDragTime(undefined);
          }}
        >
          <View
            style={[
              styles.track,
              {
                height: timelinePresentation.trackHeight,
                borderRadius: timelinePresentation.trackBorderRadius
              }
            ]}
          >
            <View
              style={[
                styles.fill,
                {
                  width: `${progressRatio * 100}%`,
                  borderRadius: timelinePresentation.trackBorderRadius
                }
              ]}
            />
            <ChapterProgressTicks ticks={chapterTicks} presentation={timelinePresentation} />
            <View
              style={[
                styles.thumb,
                {
                  left: `${progressRatio * 100}%`,
                  top: timelinePresentation.thumbTop,
                  width: timelinePresentation.thumbWidth,
                  height: timelinePresentation.thumbHeight,
                  marginLeft: timelinePresentation.thumbMarginLeft,
                  borderRadius: timelinePresentation.thumbBorderRadius
                }
              ]}
            />
          </View>
        </View>
      </View>
      {shouldShowNextEpisodeHint ? (
        <Text style={styles.nextEpisodeHint} numberOfLines={1}>
          {remainingSeconds}秒后自动播放下一集{nextEpisodeLabel ? ` · ${nextEpisodeLabel}` : ""}
        </Text>
      ) : null}
    </View>
  );
}

function formatTime(value: number) {
  const totalSeconds = Math.max(0, Math.floor(value));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

function ChapterProgressTicks({
  ticks,
  presentation
}: {
  ticks: ReturnType<typeof getChapterTicks>;
  presentation: ReturnType<typeof getTimelinePresentation>;
}) {
  if (ticks.length === 0) {
    return null;
  }
  return (
    <>
      {ticks.map((tick) => (
        <View
          key={tick.chapterId}
          style={[
            styles.chapterTick,
            {
              left: `${tick.percent}%`,
              top: presentation.tickTop,
              height: presentation.tickHeight,
              opacity: presentation.tickOpacity
            }
          ]}
        />
      ))}
    </>
  );
}

function ChapterTitleRail({
  items,
  fallbackTitle
}: {
  items: ChapterTitleRailItem[];
  fallbackTitle?: string;
}) {
  if (items.length === 0 && !fallbackTitle) {
    return null;
  }
  if (items.length === 0 && fallbackTitle) {
    return (
      <Text style={styles.chapterTitleFallback} numberOfLines={1}>
        {fallbackTitle}
      </Text>
    );
  }
  const previous = items.find((item) => item.state === "previous");
  const current = items.find((item) => item.state === "current");
  const next = items.find((item) => item.state === "next");
  return (
    <View style={styles.chapterTitleRail}>
      <Text numberOfLines={1} style={[styles.chapterTitleRailText, styles.chapterTitleNeighbor]}>
        {previous?.title ?? ""}
      </Text>
      <Text numberOfLines={1} style={[styles.chapterTitleRailText, styles.chapterTitleCurrent]}>
        {current?.title ?? fallbackTitle ?? ""}
      </Text>
      <Text numberOfLines={1} style={[styles.chapterTitleRailText, styles.chapterTitleNeighbor]}>
        {next?.title ?? ""}
      </Text>
    </View>
  );
}

function StoryboardPreview({ cell }: { cell: NonNullable<ReturnType<typeof getStoryboardCell>> }) {
  const previewWidth = 64;
  const previewHeight = Math.max(1, Math.round((previewWidth * cell.frameHeight) / cell.frameWidth));
  const scale = previewWidth / cell.frameWidth;
  return (
    <View style={[styles.storyboardFrame, { width: previewWidth, height: previewHeight }]}>
      <Image
        source={{ uri: cell.sheetUrl }}
        style={[
          styles.storyboardImage,
          {
            width: cell.sheetWidth * scale,
            height: cell.sheetHeight * scale,
            left: cell.offsetX * scale,
            top: cell.offsetY * scale
          }
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 72,
    height: 34,
    justifyContent: "center"
  },
  fullscreenScrubLayer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: -72
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg
  },
  trackTapTarget: {
    flex: 1,
    height: 24,
    justifyContent: "center"
  },
  track: {
    backgroundColor: "rgba(255,255,255,0.3)"
  },
  chapterTick: {
    position: "absolute",
    width: 2,
    marginLeft: -1,
    borderRadius: 2,
    backgroundColor: colors.text
  },
  fill: {
    height: "100%",
    backgroundColor: colors.text
  },
  thumb: {
    position: "absolute",
    backgroundColor: colors.text
  },
  nextEpisodeHint: {
    marginTop: -2,
    paddingHorizontal: spacing.lg,
    color: "rgba(255,255,255,0.62)",
    fontSize: 10,
    fontWeight: "700",
    textAlign: "right"
  },
  dragPreview: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    bottom: 44,
    alignItems: "center",
    paddingBottom: spacing.sm
  },
  storyboardFrame: {
    overflow: "hidden",
    borderRadius: radii.small,
    borderWidth: 2,
    borderColor: colors.text,
    backgroundColor: "rgba(255,255,255,0.1)"
  },
  storyboardImage: {
    position: "absolute"
  },
  chapterTitleRail: {
    width: "92%",
    marginTop: spacing.sm,
    minHeight: 24,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm
  },
  chapterTitleRailText: {
    minWidth: 0,
    textAlign: "center",
    textShadowColor: "rgba(0,0,0,0.8)",
    textShadowRadius: 6
  },
  chapterTitleFallback: {
    maxWidth: "88%",
    marginTop: spacing.sm,
    color: colors.text,
    fontSize: 17,
    fontWeight: "900",
    textAlign: "center",
    textShadowColor: "rgba(0,0,0,0.8)",
    textShadowRadius: 6
  },
  chapterTitleCurrent: {
    flex: 1.35,
    color: colors.text,
    fontSize: 17,
    fontWeight: "900"
  },
  chapterTitleNeighbor: {
    flex: 1,
    color: "rgba(255,255,255,0.42)",
    fontSize: 13,
    fontWeight: "800"
  },
  timeLabel: {
    marginTop: spacing.xs,
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
    textShadowColor: "rgba(0,0,0,0.8)",
    textShadowRadius: 6
  },
  timeTotal: {
    color: "rgba(255,255,255,0.56)"
  }
});

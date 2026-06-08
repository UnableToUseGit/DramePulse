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
import type { InteractionDebugMarker } from "../domain/interactionAssetCues";
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
  bottomOffset = 72,
  onSeekCommit,
  onDragStateChange,
  storyChapters,
  storyboard,
  debugInteractionMarkers = []
}: {
  currentTime: number;
  duration: number;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  bottomOffset?: number;
  onSeekCommit: (time: number) => void;
  onDragStateChange?: (isDragging: boolean) => void;
  storyChapters?: StoryChapter[];
  storyboard?: StoryboardManifest;
  debugInteractionMarkers?: InteractionDebugMarker[];
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
  const storyboardCell = getStoryboardCell(storyboard, visibleTime);
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
    <View style={[styles.root, { bottom: bottomOffset }]}>
      <StoryboardWarmLayer storyboard={storyboard} />
      <View pointerEvents="none" style={[styles.dragPreview, { opacity: isDragging ? 1 : 0 }]}>
        <StoryboardPreview cell={storyboardCell} isVisible={isDragging && storyboardCell !== undefined} />
        {isDragging ? <ChapterTitleRail items={chapterTitleRailItems} fallbackTitle={dragChapter?.title} /> : null}
        {isDragging ? (
          <Text style={styles.timeLabel}>
            {formatTime(visibleTime)} <Text style={styles.timeTotal}>/ {formatTime(safeDuration)}</Text>
          </Text>
        ) : null}
      </View>
      {isDragging ? (
        <View
          style={[styles.fullscreenScrubLayer, { bottom: -bottomOffset, height: viewport.height }]}
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
            <InteractionDebugMarkers markers={debugInteractionMarkers} duration={safeDuration} />
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

function InteractionDebugMarkers({
  markers,
  duration
}: {
  markers: InteractionDebugMarker[];
  duration: number;
}) {
  if (markers.length === 0 || duration <= 0) {
    return null;
  }
  return (
    <>
      {markers.map((marker) => (
        <View
          key={marker.markerId}
          pointerEvents="none"
          style={[
            styles.interactionDebugMarker,
            marker.mode === "emotional_button"
              ? styles.interactionDebugMarkerEmotion
              : styles.interactionDebugMarkerInnerVoice,
            { left: `${clamp((marker.time / duration) * 100, 0, 100)}%` }
          ]}
        />
      ))}
    </>
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

function StoryboardWarmLayer({ storyboard }: { storyboard?: StoryboardManifest }) {
  if (!storyboard || storyboard.sheets.length === 0) {
    return null;
  }
  return (
    <View pointerEvents="none" style={styles.storyboardWarmLayer}>
      {storyboard.sheets.map((sheet) => (
        <Image key={sheet.url} source={{ uri: sheet.url }} style={styles.storyboardWarmImage} />
      ))}
    </View>
  );
}

function StoryboardPreview({
  cell,
  isVisible
}: {
  cell: ReturnType<typeof getStoryboardCell>;
  isVisible: boolean;
}) {
  const previewWidth = 64;
  const fallbackFrameWidth = cell?.frameWidth ?? 16;
  const fallbackFrameHeight = cell?.frameHeight ?? 9;
  const previewHeight = Math.max(1, Math.round((previewWidth * fallbackFrameHeight) / fallbackFrameWidth));
  const scale = previewWidth / fallbackFrameWidth;
  return (
    <View style={[styles.storyboardFrame, { width: previewWidth, height: previewHeight, opacity: isVisible ? 1 : 0 }]}>
      {cell ? (
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
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    height: 34,
    justifyContent: "center"
  },
  fullscreenScrubLayer: {
    position: "absolute",
    left: 0,
    right: 0
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
  interactionDebugMarker: {
    position: "absolute",
    top: -4,
    width: 2,
    height: 11,
    marginLeft: -1,
    borderRadius: 2,
    opacity: 0.95
  },
  interactionDebugMarkerEmotion: {
    backgroundColor: "#ff8a3d"
  },
  interactionDebugMarkerInnerVoice: {
    backgroundColor: "#6ee7f2"
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
  storyboardWarmLayer: {
    position: "absolute",
    width: 1,
    height: 1,
    opacity: 0,
    overflow: "hidden"
  },
  storyboardWarmImage: {
    width: 1,
    height: 1
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

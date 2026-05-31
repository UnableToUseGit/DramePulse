import { useEffect, useRef, useState } from "react";
import { Image, LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import {
  getChapterTicks,
  getStoryboardCell,
  getStoryChapterAtTime,
  StoryboardManifest,
  StoryChapter
} from "../domain/storyNavigation";
import { colors, radii, spacing } from "../theme";

const DRAG_ACTIVATION_DISTANCE_PX = 6;

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
  const [dragTime, setDragTime] = useState<number | undefined>(undefined);
  const [trackWidth, setTrackWidth] = useState(0);
  const onSeekCommitRef = useRef(onSeekCommit);
  const dragStartXRef = useRef(0);
  const dragStartTimeRef = useRef(0);
  const didActivateDragRef = useRef(false);
  const isDragging = dragTime !== undefined;
  const visibleTime = dragTime ?? currentTime;
  const progressRatio = clamp(visibleTime / safeDuration, 0, 1);
  const remainingSeconds = Math.ceil(duration - currentTime);
  const shouldShowNextEpisodeHint = hasNextEpisode && !isDragging && remainingSeconds >= 1 && remainingSeconds <= 3;
  const chapterTicks = getChapterTicks(storyChapters, safeDuration);
  const dragChapter = isDragging ? getStoryChapterAtTime(storyChapters, visibleTime) : undefined;
  const storyboardCell = isDragging ? getStoryboardCell(storyboard, visibleTime) : undefined;

  useEffect(() => {
    onSeekCommitRef.current = onSeekCommit;
  }, [onSeekCommit]);

  useEffect(() => {
    onDragStateChange?.(isDragging);
  }, [isDragging, onDragStateChange]);

  const getTimeFromDragDelta = (deltaX: number) => {
    if (trackWidth <= 0) {
      return visibleTime;
    }
    return clamp(dragStartTimeRef.current + (deltaX / trackWidth) * safeDuration, 0, safeDuration);
  };

  const handleTrackLayout = (event: LayoutChangeEvent) => {
    setTrackWidth(event.nativeEvent.layout.width);
  };

  return (
    <View style={styles.root}>
      {isDragging ? (
        <View pointerEvents="none" style={styles.dragPreview}>
          {storyboardCell ? <StoryboardPreview cell={storyboardCell} /> : null}
          {dragChapter ? (
            <Text style={styles.chapterTitle} numberOfLines={1}>
              {dragChapter.title}
            </Text>
          ) : null}
          <Text style={styles.timeLabel}>
            {formatTime(visibleTime)} <Text style={styles.timeTotal}>/ {formatTime(safeDuration)}</Text>
          </Text>
        </View>
      ) : null}
      <View style={styles.progressRow}>
        <View
          style={styles.trackTapTarget}
          onLayout={handleTrackLayout}
          onStartShouldSetResponder={() => true}
          onMoveShouldSetResponder={() => true}
          onResponderGrant={(event) => {
            dragStartXRef.current = event.nativeEvent.pageX;
            dragStartTimeRef.current = currentTime;
            didActivateDragRef.current = false;
          }}
          onResponderMove={(event) => {
            const deltaX = event.nativeEvent.pageX - dragStartXRef.current;
            if (!didActivateDragRef.current && Math.abs(deltaX) < DRAG_ACTIVATION_DISTANCE_PX) {
              return;
            }
            didActivateDragRef.current = true;
            setDragTime(getTimeFromDragDelta(deltaX));
          }}
          onResponderRelease={(event) => {
            if (didActivateDragRef.current) {
              const nextTime = getTimeFromDragDelta(event.nativeEvent.pageX - dragStartXRef.current);
              onSeekCommitRef.current(nextTime);
            }
            didActivateDragRef.current = false;
            setDragTime(undefined);
          }}
          onResponderTerminate={() => {
            didActivateDragRef.current = false;
            setDragTime(undefined);
          }}
        >
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${progressRatio * 100}%` }]} />
            <ChapterProgressTicks ticks={chapterTicks} />
            <View style={[styles.thumb, { left: `${progressRatio * 100}%` }]} />
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

function ChapterProgressTicks({ ticks }: { ticks: ReturnType<typeof getChapterTicks> }) {
  if (ticks.length === 0) {
    return null;
  }
  return (
    <>
      {ticks.map((tick) => (
        <View key={tick.chapterId} style={[styles.chapterTick, { left: `${tick.percent}%` }]} />
      ))}
    </>
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
    height: 3,
    borderRadius: 2,
    backgroundColor: "rgba(255,255,255,0.3)"
  },
  chapterTick: {
    position: "absolute",
    top: -1,
    width: 2,
    height: 5,
    marginLeft: -1,
    borderRadius: 2,
    backgroundColor: "rgba(255,255,255,0.82)"
  },
  fill: {
    height: "100%",
    borderRadius: 2,
    backgroundColor: colors.text
  },
  thumb: {
    position: "absolute",
    top: -4,
    width: 11,
    height: 11,
    marginLeft: -5.5,
    borderRadius: 6,
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
  chapterTitle: {
    maxWidth: "88%",
    marginTop: spacing.sm,
    color: colors.text,
    fontSize: 17,
    fontWeight: "900",
    textAlign: "center",
    textShadowColor: "rgba(0,0,0,0.8)",
    textShadowRadius: 6
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

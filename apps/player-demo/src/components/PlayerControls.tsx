import { useEffect, useRef, useState } from "react";
import { GestureResponderEvent, LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

const DRAG_ACTIVATION_DISTANCE_PX = 6;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function PlayerControls({
  currentTime,
  duration,
  hasNextEpisode,
  nextEpisodeLabel,
  onSeekCommit
}: {
  currentTime: number;
  duration: number;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  onSeekCommit: (time: number) => void;
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

  useEffect(() => {
    onSeekCommitRef.current = onSeekCommit;
  }, [onSeekCommit]);

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
  }
});

import { useEffect, useRef, useState } from "react";
import Slider from "@react-native-community/slider";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

function formatTime(value: number) {
  const safeValue = Math.max(0, Math.floor(value));
  const minutes = Math.floor(safeValue / 60);
  const seconds = safeValue % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function PlayerControls({
  currentTime,
  duration,
  onSeekCommit
}: {
  currentTime: number;
  duration: number;
  onSeekCommit: (time: number) => void;
}) {
  const safeDuration = duration > 0 ? duration : 1;
  const [dragTime, setDragTime] = useState<number | undefined>(undefined);
  const onSeekCommitRef = useRef(onSeekCommit);
  const isDragging = dragTime !== undefined;
  const visibleTime = dragTime ?? currentTime;

  useEffect(() => {
    onSeekCommitRef.current = onSeekCommit;
  }, [onSeekCommit]);

  return (
    <View style={styles.root}>
      <Slider
        style={styles.track}
        minimumValue={0}
        maximumValue={safeDuration}
        value={visibleTime}
        minimumTrackTintColor={colors.text}
        maximumTrackTintColor="rgba(255,255,255,0.3)"
        thumbTintColor={colors.text}
        tapToSeek
        onSlidingStart={(value) => setDragTime(value)}
        onValueChange={(value) => setDragTime(value)}
        onSlidingComplete={(value) => {
          setDragTime(undefined);
          onSeekCommitRef.current(value);
        }}
      />
      <Text style={[styles.timeText, isDragging ? styles.draggingTimeText : null]}>
        {formatTime(visibleTime)} / {formatTime(duration)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    bottom: 76,
    height: 34,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  track: {
    flex: 1,
    height: 34
  },
  timeText: {
    width: 72,
    color: colors.text,
    fontSize: 11,
    fontWeight: "700",
    textAlign: "right"
  },
  draggingTimeText: {
    color: colors.gold
  }
});

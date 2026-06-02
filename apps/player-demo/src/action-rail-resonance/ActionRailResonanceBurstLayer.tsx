import { useEffect, useRef } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import type { ActionRailResonanceCue, ActionRailResonanceEmotionType } from "./types";

const EMOTION_BURST_COLORS: Record<ActionRailResonanceEmotionType, { primary: string; soft: string }> = {
  爽点: {
    primary: "rgba(255,106,26,0.9)",
    soft: "rgba(255,106,26,0.18)"
  },
  笑点: {
    primary: "rgba(255,209,102,0.92)",
    soft: "rgba(255,209,102,0.18)"
  },
  甜点: {
    primary: "rgba(255,123,189,0.9)",
    soft: "rgba(255,123,189,0.18)"
  },
  泪点: {
    primary: "rgba(137,200,255,0.92)",
    soft: "rgba(137,200,255,0.18)"
  }
};

export function ActionRailResonanceBurstLayer({
  cue,
  tapCount,
  releaseCount
}: {
  cue?: ActionRailResonanceCue;
  tapCount: number;
  releaseCount: number;
}) {
  const appear = useRef(new Animated.Value(0)).current;
  const ringScale = useRef(new Animated.Value(0.74)).current;
  const sparkScale = useRef(new Animated.Value(0.9)).current;

  useEffect(() => {
    if (!cue || tapCount <= 0) {
      appear.setValue(0);
      return;
    }
    appear.setValue(1);
    ringScale.setValue(releaseCount > 0 ? 0.82 : 0.68);
    sparkScale.setValue(0.88);
    Animated.parallel([
      Animated.timing(appear, {
        toValue: 0,
        duration: releaseCount > 0 ? 520 : 760,
        useNativeDriver: true
      }),
      Animated.spring(ringScale, {
        toValue: releaseCount > 0 ? 1.28 : 1.1,
        friction: 8,
        tension: 120,
        useNativeDriver: true
      }),
      Animated.spring(sparkScale, {
        toValue: releaseCount > 0 ? 1.16 : 1,
        friction: 5,
        tension: 150,
        useNativeDriver: true
      })
    ]).start();
  }, [appear, cue, releaseCount, ringScale, sparkScale, tapCount]);

  if (!cue || tapCount <= 0) {
    return null;
  }

  const burstColors = EMOTION_BURST_COLORS[cue.emotionType];
  const text = releaseCount > 0 ? `连击 x${releaseCount + 1}` : cue.feedbackText;

  return (
    <View pointerEvents="none" style={styles.root}>
      <Animated.View
        style={[
          styles.ring,
          {
            borderColor: burstColors.primary,
            backgroundColor: burstColors.soft,
            opacity: appear,
            transform: [{ scale: ringScale }]
          }
        ]}
      />
      <Animated.View
        style={[
          styles.spark,
          {
            opacity: appear,
            transform: [{ scale: sparkScale }]
          }
        ]}
      >
        <Text style={[styles.text, { color: burstColors.primary }]}>{text}</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 9
  },
  ring: {
    position: "absolute",
    width: 132,
    height: 132,
    borderRadius: 66,
    borderWidth: 2
  },
  spark: {
    minWidth: 96,
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "rgba(0,0,0,0.42)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)"
  },
  text: {
    fontSize: 15,
    fontWeight: "900",
    textShadowColor: "rgba(0,0,0,0.62)",
    textShadowRadius: 5
  }
});

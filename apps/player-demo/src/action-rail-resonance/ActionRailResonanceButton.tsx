import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { colors, playerOverlay } from "../theme";
import { CandyResonanceIcon } from "./CandyResonanceIcon";
import { SmileResonanceIcon } from "./SmileResonanceIcon";
import { TearResonanceIcon } from "./TearResonanceIcon";
import { ThrillResonanceIcon } from "./ThrillResonanceIcon";
import { formatResonanceCount, getParticipatingCount } from "./formatCount";
import { reduceResonanceTap, ResonanceTapState } from "./tapState";
import type { ActionRailResonanceCue, ActionRailResonanceEmotionType } from "./types";

const EMOTION_COLORS: Record<ActionRailResonanceEmotionType, { primary: string; glow: string }> = {
  爽点: {
    primary: "#ff6a1a",
    glow: "rgba(255,106,26,0.48)"
  },
  笑点: {
    primary: "#ffd166",
    glow: "rgba(255,209,102,0.42)"
  },
  甜点: {
    primary: "#ff7bbd",
    glow: "rgba(255,123,189,0.44)"
  },
  泪点: {
    primary: "#89c8ff",
    glow: "rgba(137,200,255,0.42)"
  }
};

export function ActionRailResonanceButton({
  cue,
  tapState,
  onParticipate
}: {
  cue: ActionRailResonanceCue;
  tapState: ResonanceTapState;
  onParticipate: (cue: ActionRailResonanceCue, nextState: ResonanceTapState) => void;
}) {
  const scale = useRef(new Animated.Value(1)).current;
  const attention = useRef(new Animated.Value(0)).current;
  const colorsForEmotion = EMOTION_COLORS[cue.emotionType];
  const hasParticipated = tapState.phase !== "idle";
  const isThrillCue = cue.emotionType === "爽点";
  const isCandyCue = cue.emotionType === "甜点";
  const isLaughCue = cue.emotionType === "笑点";
  const isTearCue = cue.emotionType === "泪点";
  const countText = useMemo(
    () => formatResonanceCount(getParticipatingCount({ baseCount: cue.baseCount, hasParticipated })),
    [cue.baseCount, hasParticipated]
  );

  const pulse = useCallback((isReleaseTap: boolean) => {
    scale.stopAnimation();
    scale.setValue(isReleaseTap ? 0.84 : 0.9);
    Animated.spring(scale, {
      toValue: 1,
      friction: isReleaseTap ? 3 : 5,
      tension: isReleaseTap ? 230 : 180,
      useNativeDriver: true
    }).start();
  }, [scale]);

  const handlePress = useCallback(() => {
    const nextState = reduceResonanceTap(tapState);
    const isReleaseTap = nextState.action === "release";
    pulse(isReleaseTap);
    if (isReleaseTap) {
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    } else {
      void Haptics.selectionAsync();
    }
    onParticipate(cue, nextState);
  }, [cue, onParticipate, pulse, tapState]);

  useEffect(() => {
    scale.setValue(1);
  }, [cue.cueId, scale]);

  useEffect(() => {
    if (hasParticipated) {
      attention.stopAnimation();
      attention.setValue(0);
      return;
    }

    attention.setValue(0);
    const loop = Animated.loop(
      Animated.timing(attention, {
        toValue: 1,
        duration: 1500,
        useNativeDriver: true
      })
    );
    loop.start();
    return () => loop.stop();
  }, [attention, cue.cueId, hasParticipated]);

  const attentionOpacity = attention.interpolate({
    inputRange: [0, 0.16, 1],
    outputRange: [0, 0.62, 0]
  });
  const attentionScale = attention.interpolate({
    inputRange: [0, 1],
    outputRange: [0.78, 1.45]
  });
  const secondaryAttentionOpacity = attention.interpolate({
    inputRange: [0, 0.36, 1],
    outputRange: [0, 0.46, 0]
  });
  const secondaryAttentionScale = attention.interpolate({
    inputRange: [0, 1],
    outputRange: [0.56, 1.76]
  });

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={cue.label}
      accessibilityState={{ selected: hasParticipated }}
      disabled={hasParticipated}
      style={styles.root}
      onPress={handlePress}
    >
      <Animated.View style={[styles.iconShell, { transform: [{ scale }] }]}>
        {!hasParticipated ? (
          <>
            <Animated.View
              style={[
                styles.attentionHalo,
                {
                  backgroundColor: colorsForEmotion.glow,
                  opacity: attentionOpacity,
                  transform: [{ scale: attentionScale }]
                }
              ]}
            />
            <Animated.View
              style={[
                styles.attentionHalo,
                styles.attentionHaloSecondary,
                {
                  borderColor: colorsForEmotion.primary,
                  opacity: secondaryAttentionOpacity,
                  transform: [{ scale: secondaryAttentionScale }]
                }
              ]}
            />
          </>
        ) : null}
        {isThrillCue || isCandyCue || isLaughCue || isTearCue ? (
          <View style={styles.plainIconWrap}>
            {isThrillCue ? (
              <ThrillResonanceIcon isLit={hasParticipated} size={58} />
            ) : isCandyCue ? (
              <CandyResonanceIcon isLit={hasParticipated} />
            ) : isLaughCue ? (
              <SmileResonanceIcon isLit={hasParticipated} size={62} />
            ) : (
              <TearResonanceIcon isLit={hasParticipated} size={62} />
            )}
          </View>
        ) : (
          <>
            <View
              style={[
                styles.glow,
                { backgroundColor: hasParticipated ? colorsForEmotion.glow : "rgba(255,255,255,0.1)" }
              ]}
            />
            <View
              style={[
                styles.iconCircle,
                {
                  borderColor: colorsForEmotion.primary,
                  backgroundColor: hasParticipated ? colorsForEmotion.glow : "rgba(0,0,0,0.48)"
                }
              ]}
            >
              <Ionicons name={cue.icon} size={28} color={hasParticipated ? colorsForEmotion.primary : "#f4f4f4"} />
            </View>
          </>
        )}
      </Animated.View>
      <Text style={styles.count}>{countText}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    alignItems: "center",
    width: 56,
    gap: 1
  },
  iconShell: {
    width: 48,
    height: 42,
    alignItems: "center",
    justifyContent: "center"
  },
  plainIconWrap: {
    width: 48,
    height: 40,
    alignItems: "center",
    justifyContent: "center"
  },
  attentionHalo: {
    position: "absolute",
    width: 48,
    height: 48,
    borderRadius: 24
  },
  attentionHaloSecondary: {
    backgroundColor: "transparent",
    borderWidth: 1.4
  },
  glow: {
    position: "absolute",
    width: 48,
    height: 48,
    borderRadius: 24
  },
  iconCircle: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 22,
    borderWidth: 1.5,
    backgroundColor: "rgba(0,0,0,0.48)"
  },
  count: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
    ...playerOverlay.textShadow
  },
});

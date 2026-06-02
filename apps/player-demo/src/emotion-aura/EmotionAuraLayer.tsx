import { useEffect, useMemo, useRef } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import type { EmotionAuraCue, EmotionEnergyLevel, EmotionAuraType } from "./types";

type AuraPalette = {
  edge: string;
  pulse: string;
  text: string;
  particle: string;
  symbol: string;
};

const PALETTES: Record<EmotionAuraType, AuraPalette> = {
  爽点: {
    edge: "rgba(255,88,32,0.34)",
    pulse: "rgba(255,132,45,0.76)",
    text: "#FFE2C7",
    particle: "rgba(255,198,104,0.88)",
    symbol: "!"
  },
  笑点: {
    edge: "rgba(255,218,86,0.30)",
    pulse: "rgba(255,221,92,0.78)",
    text: "#FFF1B8",
    particle: "rgba(255,245,164,0.92)",
    symbol: "ha"
  },
  甜点: {
    edge: "rgba(255,139,177,0.30)",
    pulse: "rgba(255,177,211,0.78)",
    text: "#FFE4F0",
    particle: "rgba(255,231,243,0.92)",
    symbol: "♡"
  },
  泪点: {
    edge: "rgba(150,190,255,0.26)",
    pulse: "rgba(177,209,255,0.72)",
    text: "#DDEBFF",
    particle: "rgba(207,226,255,0.88)",
    symbol: "..."
  }
};

export function EmotionAuraLayer({
  cue,
  tapCount,
  energyLevel,
  isSettled,
  lastTapPoint,
  showExpression
}: {
  cue: EmotionAuraCue;
  tapCount: number;
  energyLevel: EmotionEnergyLevel;
  isSettled: boolean;
  lastTapPoint?: { x: number; y: number };
  showExpression: boolean;
}) {
  const appear = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(0)).current;
  const palette = PALETTES[cue.emotionType];

  useEffect(() => {
    appear.setValue(0);
    Animated.timing(appear, {
      toValue: 1,
      duration: 420,
      useNativeDriver: true
    }).start();
  }, [appear, cue.cueId]);

  useEffect(() => {
    if (tapCount <= 0) {
      return;
    }
    pulse.setValue(0);
    Animated.timing(pulse, {
      toValue: 1,
      duration: cue.emotionType === "泪点" ? 620 : 360,
      useNativeDriver: true
    }).start();
  }, [cue.emotionType, pulse, tapCount]);

  const particles = useMemo(() => createParticles(cue.cueId, energyLevel), [cue.cueId, energyLevel]);
  const intensity = energyLevel === "high" ? 1 : energyLevel === "medium" ? 0.72 : 0.46;
  const feedbackTopOffset = isSettled ? 100 : 72;

  return (
    <View pointerEvents="none" style={styles.root}>
      <Animated.View
        style={[
          styles.edgeGlow,
          {
            borderColor: palette.edge,
            shadowColor: palette.pulse,
            opacity: appear.interpolate({ inputRange: [0, 1], outputRange: [0, 0.62 + intensity * 0.24] })
          }
        ]}
      />
      {showExpression && lastTapPoint ? (
        <Animated.View
          style={[
            styles.pulse,
            {
              borderColor: palette.pulse,
              opacity: pulse.interpolate({ inputRange: [0, 0.28, 1], outputRange: [0, 0.92, 0] }),
              left: lastTapPoint.x - 75,
              top: lastTapPoint.y - 75,
              transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.46, 1.54 + intensity * 0.32] }) }]
            }
          ]}
        />
      ) : null}
      {showExpression && lastTapPoint
        ? particles.map((particle, index) => (
            <Animated.View
              key={particle.id}
              style={[
                styles.particle,
                {
                  left: lastTapPoint.x + particle.offsetX,
                  top: lastTapPoint.y + particle.offsetY,
                  backgroundColor: palette.particle,
                  opacity: pulse.interpolate({ inputRange: [0, 0.2, 1], outputRange: [0, particle.opacity, 0] }),
                  transform: [
                    { translateY: pulse.interpolate({ inputRange: [0, 1], outputRange: [0, -particle.travel] }) },
                    { scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.7, particle.scale] }) }
                  ]
                }
              ]}
            >
              {index % 3 === 0 ? <Text style={styles.symbol}>{palette.symbol}</Text> : null}
            </Animated.View>
          ))
        : null}
      {showExpression && lastTapPoint ? (
        <Animated.View
          style={[
            styles.floatingFeedback,
            {
              left: Math.max(18, lastTapPoint.x - 96),
              top: Math.max(92, lastTapPoint.y - feedbackTopOffset),
              opacity: appear,
              transform: [{ translateY: pulse.interpolate({ inputRange: [0, 1], outputRange: [0, -8] }) }]
            }
          ]}
        >
          <Text style={[styles.label, { color: palette.text }]}>{isSettled ? cue.resonanceText : `${tapCount} 连击`}</Text>
          {isSettled ? <Text style={styles.hint}>情绪已收到</Text> : null}
        </Animated.View>
      ) : null}
    </View>
  );
}

function createParticles(cueId: string, energyLevel: EmotionEnergyLevel) {
  const count = energyLevel === "high" ? 12 : energyLevel === "medium" ? 8 : 5;
  return Array.from({ length: count }, (_, index) => ({
    id: `${cueId}-${index}`,
    offsetX: -34 + ((index * 17) % 68),
    offsetY: -22 + ((index * 11) % 44),
    travel: 28 + ((index * 13) % 64),
    opacity: 0.42 + ((index % 4) * 0.13),
    scale: 0.8 + ((index % 5) * 0.16)
  }));
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    overflow: "hidden"
  },
  edgeGlow: {
    ...StyleSheet.absoluteFillObject,
    borderWidth: 10,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.86,
    shadowRadius: 24
  },
  pulse: {
    position: "absolute",
    width: 150,
    height: 150,
    borderRadius: 75,
    borderWidth: 2
  },
  particle: {
    position: "absolute",
    width: 9,
    height: 9,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill
  },
  symbol: {
    marginTop: -7,
    color: colors.text,
    fontSize: 10,
    fontWeight: "900"
  },
  floatingFeedback: {
    position: "absolute",
    alignItems: "center",
    maxWidth: 230,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
    borderRadius: radii.panel,
    backgroundColor: "rgba(0,0,0,0.24)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)"
  },
  label: {
    fontSize: 16,
    fontWeight: "900",
    textAlign: "center"
  },
  hint: {
    marginTop: 3,
    color: colors.muted,
    fontSize: 11,
    fontWeight: "800",
    textAlign: "center"
  }
});

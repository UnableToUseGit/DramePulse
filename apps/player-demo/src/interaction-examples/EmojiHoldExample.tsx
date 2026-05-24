import { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import type { InteractionExample } from "./types";

const BURST_EMOJIS = ["🔥", "✨", "💥", "🔥", "✨"];

export function EmojiHoldExample({ example, onDismiss }: { example: InteractionExample; onDismiss: () => void }) {
  const [isHolding, setIsHolding] = useState(false);
  const [hasBurst, setHasBurst] = useState(false);
  const pulse = useRef(new Animated.Value(0)).current;
  const burst = useRef(new Animated.Value(0)).current;
  const primaryReaction = example.reactions[0];

  useEffect(() => {
    setIsHolding(false);
    setHasBurst(false);
    pulse.setValue(0);
    burst.setValue(0);
  }, [burst, example.id, pulse]);

  useEffect(() => {
    if (!isHolding) {
      pulse.stopAnimation();
      Animated.timing(pulse, {
        toValue: 0,
        duration: 180,
        useNativeDriver: true
      }).start();
      return;
    }

    Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 620,
          useNativeDriver: true
        }),
        Animated.timing(pulse, {
          toValue: 0.25,
          duration: 420,
          useNativeDriver: true
        })
      ])
    ).start();
  }, [isHolding, pulse]);

  const triggerBurst = () => {
    setIsHolding(false);
    setHasBurst(true);
    burst.setValue(0);
    Animated.timing(burst, {
      toValue: 1,
      duration: 780,
      useNativeDriver: true
    }).start(() => {
      setHasBurst(false);
      onDismiss();
    });
  };

  const ringScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.75]
  });
  const ringOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.22, 0.02]
  });
  const buttonScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.12]
  });

  return (
    <View style={styles.root} pointerEvents="box-none">
      {hasBurst ? (
        <Animated.View
          style={[
            styles.burstLayer,
            {
              opacity: burst.interpolate({ inputRange: [0, 0.3, 1], outputRange: [0, 1, 0] }),
              transform: [
                { scale: burst.interpolate({ inputRange: [0, 1], outputRange: [0.8, 1.35] }) },
                { translateY: burst.interpolate({ inputRange: [0, 1], outputRange: [0, -34] }) }
              ]
            }
          ]}
        >
          {BURST_EMOJIS.map((emoji, index) => (
            <Text key={`${emoji}-${index}`} style={[styles.burstEmoji, index % 2 === 0 ? styles.burstHigh : null]}>
              {emoji}
            </Text>
          ))}
        </Animated.View>
      ) : null}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={example.prompt}
        onPressIn={() => setIsHolding(true)}
        onPressOut={triggerBurst}
      >
        <View style={styles.buttonWrap}>
          <Animated.View style={[styles.pulseRing, { opacity: ringOpacity, transform: [{ scale: ringScale }] }]} />
          <Animated.View style={[styles.button, { transform: [{ scale: buttonScale }] }]}>
            <Text style={styles.emoji}>{primaryReaction.emoji}</Text>
          </Animated.View>
        </View>
      </Pressable>
      <View style={styles.caption}>
        <Text style={styles.prompt}>{example.prompt}</Text>
        <Text style={styles.hint}>长按释放情绪</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    right: spacing.lg,
    top: "48%",
    alignItems: "center"
  },
  buttonWrap: {
    width: 82,
    height: 82,
    alignItems: "center",
    justifyContent: "center"
  },
  pulseRing: {
    position: "absolute",
    width: 78,
    height: 78,
    borderRadius: 39,
    backgroundColor: colors.accent,
    borderWidth: 1,
    borderColor: "rgba(255,213,138,0.9)"
  },
  button: {
    width: 62,
    height: 62,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,106,26,0.94)",
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.82)",
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.45,
    shadowRadius: 18
  },
  emoji: {
    fontSize: 30
  },
  caption: {
    width: 116,
    marginTop: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.small,
    backgroundColor: "rgba(0,0,0,0.46)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)"
  },
  prompt: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "900",
    textAlign: "center"
  },
  hint: {
    marginTop: 2,
    color: colors.gold,
    fontSize: 10,
    fontWeight: "900",
    textAlign: "center"
  },
  burstLayer: {
    position: "absolute",
    top: -12,
    right: -6,
    width: 124,
    height: 84,
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "center"
  },
  burstEmoji: {
    marginHorizontal: 2,
    fontSize: 23
  },
  burstHigh: {
    marginTop: -18
  }
});

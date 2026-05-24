import { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { colors, radii, spacing } from "../theme";
import type { InteractionExample } from "./types";

const BURST_EMOJIS = ["🔥", "✨", "💥", "🔥", "✨"];
const HOLD_DURATION_MS = 2000;
const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const PROGRESS_RADIUS = 40;
const PROGRESS_CIRCUMFERENCE = 2 * Math.PI * PROGRESS_RADIUS;

export function EmojiHoldExample({ example, onDismiss }: { example: InteractionExample; onDismiss: () => void }) {
  const [isHolding, setIsHolding] = useState(false);
  const [hasBurst, setHasBurst] = useState(false);
  const [isCharging, setIsCharging] = useState(true);
  const charge = useRef(new Animated.Value(0)).current;
  const burst = useRef(new Animated.Value(0)).current;
  const holdCompletedRef = useRef(false);
  const primaryReaction = example.reactions[0];

  useEffect(() => {
    setIsHolding(false);
    setHasBurst(false);
    setIsCharging(true);
    holdCompletedRef.current = false;
    charge.setValue(0);
    burst.setValue(0);
  }, [burst, charge, example.id]);

  const triggerBurst = () => {
    if (holdCompletedRef.current) {
      return;
    }
    holdCompletedRef.current = true;
    setIsHolding(false);
    setIsCharging(false);
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

  const handlePressIn = () => {
    if (!isCharging) {
      return;
    }
    setIsHolding(true);
    charge.setValue(0);
    Animated.timing(charge, {
      toValue: 1,
      duration: HOLD_DURATION_MS,
      useNativeDriver: false
    }).start(({ finished }) => {
      if (finished) {
        triggerBurst();
      }
    });
  };

  const handlePressOut = () => {
    if (!isCharging || holdCompletedRef.current) {
      return;
    }
    setIsHolding(false);
    charge.stopAnimation();
    Animated.timing(charge, {
      toValue: 0,
      duration: 180,
      useNativeDriver: false
    }).start();
  };

  const ringScale = charge.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.08]
  });
  const ringOpacity = charge.interpolate({
    inputRange: [0, 1],
    outputRange: [0.18, 0.82]
  });
  const progressOffset = charge.interpolate({
    inputRange: [0, 1],
    outputRange: [PROGRESS_CIRCUMFERENCE, 0]
  });
  const buttonScale = charge.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.16]
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
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        disabled={!isCharging}
      >
        <View style={styles.buttonWrap}>
          <Animated.View style={[styles.outerGlow, { opacity: ringOpacity, transform: [{ scale: ringScale }] }]} />
          <Svg width={94} height={94} style={styles.progressSvg} viewBox="0 0 94 94">
            <Circle
              cx={47}
              cy={47}
              r={PROGRESS_RADIUS}
              stroke="rgba(255,255,255,0.2)"
              strokeWidth={5}
              fill="transparent"
            />
            <AnimatedCircle
              cx={47}
              cy={47}
              r={PROGRESS_RADIUS}
              stroke={colors.gold}
              strokeWidth={5}
              fill="transparent"
              strokeLinecap="round"
              strokeDasharray={`${PROGRESS_CIRCUMFERENCE} ${PROGRESS_CIRCUMFERENCE}`}
              strokeDashoffset={progressOffset}
              transform="rotate(-90 47 47)"
            />
          </Svg>
          <Animated.View style={[styles.button, { transform: [{ scale: buttonScale }] }]}>
            <Text style={styles.emoji}>{primaryReaction.emoji}</Text>
          </Animated.View>
        </View>
      </Pressable>
      <View style={styles.caption}>
        <Text style={styles.prompt}>{isHolding ? "继续按住" : example.prompt}</Text>
        <Text style={styles.hint}>蓄力 2 秒释放</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    right: 22,
    bottom: 176,
    alignItems: "center"
  },
  buttonWrap: {
    width: 94,
    height: 94,
    alignItems: "center",
    justifyContent: "center"
  },
  outerGlow: {
    position: "absolute",
    width: 92,
    height: 92,
    borderRadius: 46,
    backgroundColor: colors.accent,
    borderWidth: 1,
    borderColor: "rgba(255,213,138,0.9)"
  },
  progressSvg: {
    position: "absolute",
    width: 94,
    height: 94
  },
  button: {
    width: 66,
    height: 66,
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
    fontSize: 32
  },
  caption: {
    width: 118,
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
    top: -22,
    right: -14,
    width: 138,
    height: 96,
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

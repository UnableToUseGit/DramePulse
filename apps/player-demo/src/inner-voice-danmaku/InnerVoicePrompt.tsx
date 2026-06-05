import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useEffect, useMemo, useRef } from "react";
import { PanResponder, StyleSheet, Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withDecay,
  withDelay,
  withSequence,
  withSpring,
  withTiming
} from "react-native-reanimated";
import { colors, radii, spacing } from "../theme";
import {
  getInnerVoiceDragState,
  getInnerVoiceFlingVelocity,
  shouldClaimInnerVoiceDrag,
  shouldSendInnerVoiceDraft
} from "./gesture";
import type { InnerVoiceDanmakuCue } from "./types";

const LAUNCH_DECELERATION = 0.994;
const LAUNCH_X_CLAMP: [number, number] = [-180, 180];
const LAUNCH_Y_CLAMP: [number, number] = [-520, 60];
const ENTRY_OFFSET_X = -28;
const ENTRY_OFFSET_Y = 8;
const BUBBLE_ENTRY_SCALE = 0.34;
const ENTRY_FADE_MS = 260;
const ENTRY_TRAVEL_MS = 620;
const BUBBLE_BREATH_MS = 680;
const CONTENT_REVEAL_DELAY_MS = 260;
const CONTENT_REVEAL_MS = 260;

export function InnerVoicePrompt({
  cue,
  onSend,
  onGestureActiveChange,
  onExitComplete
}: {
  cue: InnerVoiceDanmakuCue;
  onSend: (cue: InnerVoiceDanmakuCue) => void;
  onGestureActiveChange: (active: boolean) => void;
  onExitComplete: (cue: InnerVoiceDanmakuCue) => void;
}) {
  const appear = useSharedValue(0);
  const entryTranslateX = useSharedValue(ENTRY_OFFSET_X);
  const entryTranslateY = useSharedValue(ENTRY_OFFSET_Y);
  const bubbleScale = useSharedValue(BUBBLE_ENTRY_SCALE);
  const bubbleBreath = useSharedValue(0);
  const contentReveal = useSharedValue(0);
  const dragX = useSharedValue(0);
  const dragY = useSharedValue(0);
  const launchScale = useSharedValue(1);
  const didSendRef = useRef(false);

  useEffect(() => {
    appear.value = 0;
    entryTranslateX.value = ENTRY_OFFSET_X;
    entryTranslateY.value = ENTRY_OFFSET_Y;
    bubbleScale.value = BUBBLE_ENTRY_SCALE;
    bubbleBreath.value = 0;
    contentReveal.value = 0;
    dragX.value = 0;
    dragY.value = 0;
    launchScale.value = 1;
    didSendRef.current = false;
    appear.value = withTiming(1, {
      duration: ENTRY_FADE_MS,
      easing: Easing.out(Easing.quad)
    });
    entryTranslateX.value = withTiming(0, {
      duration: ENTRY_TRAVEL_MS,
      easing: Easing.out(Easing.cubic)
    });
    entryTranslateY.value = withSpring(0, {
      damping: 14,
      stiffness: 170,
      mass: 0.8
    });
    bubbleScale.value = withSequence(
      withTiming(1.08, {
        duration: BUBBLE_BREATH_MS,
        easing: Easing.out(Easing.cubic)
      }),
      withSpring(1, {
        damping: 18,
        stiffness: 210,
        mass: 0.7
      })
    );
    bubbleBreath.value = withTiming(1, {
      duration: BUBBLE_BREATH_MS,
      easing: Easing.out(Easing.quad)
    });
    contentReveal.value = withDelay(CONTENT_REVEAL_DELAY_MS, withTiming(1, {
      duration: CONTENT_REVEAL_MS,
      easing: Easing.out(Easing.quad)
    }));
  }, [
    appear,
    bubbleBreath,
    bubbleScale,
    contentReveal,
    cue.cueId,
    dragX,
    dragY,
    entryTranslateX,
    entryTranslateY,
    launchScale
  ]);

  const bubbleBreathStyle = useAnimatedStyle(() => ({
    opacity: (1 - bubbleBreath.value) * appear.value,
    transform: [
      { translateX: -12 + bubbleBreath.value * 7 },
      { translateY: 4 - bubbleBreath.value * 5 },
      { scale: 0.62 + bubbleBreath.value * 1.2 }
    ]
  }));

  const contentRevealStyle = useAnimatedStyle(() => ({
    opacity: contentReveal.value,
    transform: [
      { translateX: (1 - contentReveal.value) * -4 },
      { scale: 0.98 + contentReveal.value * 0.02 }
    ]
  }));

  const animatedDraftStyle = useAnimatedStyle(() => ({
    opacity: appear.value,
    transform: [
      { translateX: entryTranslateX.value },
      { translateY: entryTranslateY.value },
      { translateX: dragX.value },
      { translateY: dragY.value },
      { scale: bubbleScale.value * launchScale.value }
    ]
  }));

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onPanResponderGrant: () => {
          void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
          cancelAnimation(dragX);
          cancelAnimation(dragY);
          cancelAnimation(appear);
          cancelAnimation(bubbleScale);
          cancelAnimation(bubbleBreath);
          cancelAnimation(contentReveal);
          cancelAnimation(launchScale);
          bubbleScale.value = 1;
          bubbleBreath.value = 1;
          contentReveal.value = 1;
          launchScale.value = 1;
          onGestureActiveChange(true);
        },
        onMoveShouldSetPanResponder: (_, gesture) => shouldClaimInnerVoiceDrag({ dx: gesture.dx, dy: gesture.dy }),
        onPanResponderTerminationRequest: () => false,
        onPanResponderMove: (_, gesture) => {
          if (didSendRef.current) {
            return;
          }
          const dragState = getInnerVoiceDragState({ dx: gesture.dx, dy: gesture.dy });
          dragX.value = dragState.translateX;
          dragY.value = dragState.translateY;
        },
        onPanResponderRelease: (_, gesture) => {
          if (didSendRef.current) {
            return;
          }
          if (shouldSendInnerVoiceDraft({ dx: gesture.dx, dy: gesture.dy })) {
            didSendRef.current = true;
            onSend(cue);
            const { velocityX, velocityY } = getInnerVoiceFlingVelocity({ vx: gesture.vx, vy: gesture.vy });
            const completeLaunch = () => {
              onGestureActiveChange(false);
              onExitComplete(cue);
            };

            dragX.value = withDecay({
              velocity: velocityX,
              deceleration: LAUNCH_DECELERATION,
              clamp: LAUNCH_X_CLAMP
            });
            dragY.value = withDecay({
              velocity: velocityY,
              deceleration: LAUNCH_DECELERATION,
              clamp: LAUNCH_Y_CLAMP
            });
            launchScale.value = withTiming(0.76, {
              duration: 420,
              easing: Easing.out(Easing.cubic)
            });
            appear.value = withDelay(
              110,
              withTiming(
                0,
                {
                  duration: 300,
                  easing: Easing.out(Easing.quad)
                },
                (finished) => {
                  if (finished) {
                    runOnJS(completeLaunch)();
                  }
                }
              )
            );
            return;
          }
          dragX.value = withSpring(0);
          dragY.value = withSpring(0);
          onGestureActiveChange(false);
        },
        onPanResponderTerminate: () => {
          if (didSendRef.current) {
            return;
          }
          dragX.value = withSpring(0);
          dragY.value = withSpring(0);
          onGestureActiveChange(false);
        }
      }),
    [
      appear,
      bubbleBreath,
      bubbleScale,
      contentReveal,
      cue,
      dragX,
      dragY,
      launchScale,
      onExitComplete,
      onGestureActiveChange,
      onSend
    ]
  );

  return (
    <View pointerEvents="box-none" style={styles.root}>
      <Animated.View
        {...panResponder.panHandlers}
        accessibilityRole="button"
        accessibilityLabel={`发送心里话弹幕：${cue.text}`}
        style={[styles.draft, animatedDraftStyle]}
      >
        <Animated.View pointerEvents="none" style={[styles.bubbleBreath, bubbleBreathStyle]} />
        <Animated.View style={[styles.draftContent, contentRevealStyle]}>
          <Ionicons name="chatbubble" size={14} color={colors.gold} />
          <Text numberOfLines={1} style={styles.draftText}>
            {cue.text}
          </Text>
          <Ionicons name="arrow-up" size={14} color="rgba(255,213,138,0.9)" />
        </Animated.View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    alignSelf: "flex-start",
    flexShrink: 1,
    minWidth: 0,
    overflow: "visible"
  },
  draft: {
    alignSelf: "flex-start",
    maxWidth: 220,
    height: 36,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: "rgba(0,0,0,0.46)",
    borderWidth: 1,
    borderColor: "rgba(255,213,138,0.26)",
    shadowColor: "#FFD58A",
    shadowOpacity: 0.18,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
    overflow: "visible"
  },
  bubbleBreath: {
    position: "absolute",
    left: 3,
    top: 5,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(255,213,138,0.2)",
    borderWidth: 1,
    borderColor: "rgba(255,213,138,0.46)"
  },
  draftContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7
  },
  draftText: {
    flexShrink: 1,
    color: colors.text,
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0
  }
});

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
  const dragX = useSharedValue(0);
  const dragY = useSharedValue(0);
  const launchScale = useSharedValue(1);
  const didSendRef = useRef(false);

  useEffect(() => {
    appear.value = 0;
    dragX.value = 0;
    dragY.value = 0;
    launchScale.value = 1;
    didSendRef.current = false;
    appear.value = withSpring(1, {
      damping: 16,
      stiffness: 180,
      mass: 0.8
    });
  }, [appear, cue.cueId, dragX, dragY, launchScale]);

  const animatedDraftStyle = useAnimatedStyle(() => ({
    opacity: appear.value,
    transform: [
      { translateX: dragX.value },
      { translateY: dragY.value },
      { scale: launchScale.value * (0.96 + appear.value * 0.04) }
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
          cancelAnimation(launchScale);
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
    [appear, cue, dragX, dragY, launchScale, onExitComplete, onGestureActiveChange, onSend]
  );

  return (
    <View pointerEvents="box-none" style={styles.root}>
      <Animated.View
        {...panResponder.panHandlers}
        accessibilityRole="button"
        accessibilityLabel={`发送心里话弹幕：${cue.text}`}
        style={[styles.draft, animatedDraftStyle]}
      >
        <Ionicons name="chatbubble" size={14} color={colors.gold} />
        <Text numberOfLines={1} style={styles.draftText}>
          {cue.text}
        </Text>
        <Ionicons name="arrow-up" size={14} color="rgba(255,213,138,0.9)" />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flexShrink: 1,
    minWidth: 0,
    overflow: "visible"
  },
  draft: {
    maxWidth: 220,
    height: 36,
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: "rgba(8,8,10,0.76)",
    borderWidth: 1,
    borderColor: "rgba(255,213,138,0.26)",
    shadowColor: "#FFD58A",
    shadowOpacity: 0.18,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
    overflow: "visible"
  },
  draftText: {
    flexShrink: 1,
    color: colors.text,
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0
  }
});

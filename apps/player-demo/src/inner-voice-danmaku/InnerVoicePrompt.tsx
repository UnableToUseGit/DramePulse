import { Ionicons } from "@expo/vector-icons";
import { useEffect, useRef } from "react";
import { Animated, Easing, PanResponder, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";
import {
  getInnerVoiceDragState,
  getInnerVoiceLaunchTarget,
  shouldClaimInnerVoiceDrag,
  shouldSendInnerVoiceDraft
} from "./gesture";
import type { InnerVoiceDanmakuCue } from "./types";

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
  const appear = useRef(new Animated.Value(0)).current;
  const dragX = useRef(new Animated.Value(0)).current;
  const dragY = useRef(new Animated.Value(0)).current;
  const launchScale = useRef(new Animated.Value(1)).current;
  const didSendRef = useRef(false);

  useEffect(() => {
    appear.setValue(0);
    dragX.setValue(0);
    dragY.setValue(0);
    launchScale.setValue(1);
    didSendRef.current = false;
    Animated.spring(appear, {
      toValue: 1,
      damping: 16,
      stiffness: 180,
      mass: 0.8,
      useNativeDriver: true
    }).start();
  }, [appear, cue.cueId, dragX, dragY, launchScale]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        onGestureActiveChange(true);
      },
      onMoveShouldSetPanResponder: (_, gesture) => shouldClaimInnerVoiceDrag({ dx: gesture.dx, dy: gesture.dy }),
      onPanResponderTerminationRequest: () => false,
      onPanResponderMove: (_, gesture) => {
        if (didSendRef.current) {
          return;
        }
        const dragState = getInnerVoiceDragState({ dx: gesture.dx, dy: gesture.dy });
        dragX.setValue(dragState.translateX);
        dragY.setValue(dragState.translateY);
      },
      onPanResponderRelease: (_, gesture) => {
        if (didSendRef.current) {
          return;
        }
        if (shouldSendInnerVoiceDraft({ dx: gesture.dx, dy: gesture.dy })) {
          didSendRef.current = true;
          onSend(cue);
          const launchTarget = getInnerVoiceLaunchTarget({ dx: gesture.dx, dy: gesture.dy, vy: gesture.vy });
          Animated.parallel([
            Animated.timing(dragX, {
              toValue: launchTarget.translateX,
              duration: 340,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true
            }),
            Animated.timing(dragY, {
              toValue: launchTarget.translateY,
              duration: 340,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true
            }),
            Animated.timing(appear, {
              toValue: 0,
              duration: 260,
              delay: 70,
              easing: Easing.out(Easing.quad),
              useNativeDriver: true
            }),
            Animated.timing(launchScale, {
              toValue: 0.92,
              duration: 340,
              easing: Easing.out(Easing.cubic),
              useNativeDriver: true
            })
          ]).start(() => {
            onGestureActiveChange(false);
            onExitComplete(cue);
          });
          return;
        }
        Animated.spring(dragX, { toValue: 0, useNativeDriver: true }).start();
        Animated.spring(dragY, { toValue: 0, useNativeDriver: true }).start();
        onGestureActiveChange(false);
      },
      onPanResponderTerminate: () => {
        if (didSendRef.current) {
          return;
        }
        Animated.spring(dragX, { toValue: 0, useNativeDriver: true }).start();
        Animated.spring(dragY, { toValue: 0, useNativeDriver: true }).start();
        onGestureActiveChange(false);
      }
    })
  ).current;

  return (
    <View pointerEvents="box-none" style={styles.root}>
      <Animated.View
        {...panResponder.panHandlers}
        accessibilityRole="button"
        accessibilityLabel={`发送心里话弹幕：${cue.text}`}
        style={[
          styles.draft,
          {
            opacity: appear,
            transform: [
              { translateX: dragX },
              { translateY: dragY },
              { scale: Animated.multiply(launchScale, appear.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] })) }
            ]
          }
        ]}
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

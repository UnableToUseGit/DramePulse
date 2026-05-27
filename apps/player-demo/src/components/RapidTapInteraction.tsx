import { useCallback, useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet } from "react-native";
import { RapidTapSurprise } from "./RapidTapSurprise";

const RAPID_TAP_WINDOW_MS = 4200;
const BURST_SETTLE_MS = 760;
const BURST_LAYER_LIFETIME_MS = 900;

export function RapidTapInteraction({
  enabled,
  isActive,
  isStarted,
  currentTime,
  triggerTimeSec,
  promptDurationSec,
  resetKey
}: {
  enabled: boolean;
  isActive: boolean;
  isStarted: boolean;
  currentTime: number;
  triggerTimeSec: number;
  promptDurationSec: number;
  resetKey: string;
}) {
  const [tapCount, setTapCount] = useState(0);
  const [burstCount, setBurstCount] = useState(0);
  const [burstVersion, setBurstVersion] = useState(0);
  const [isBurstLayerVisible, setIsBurstLayerVisible] = useState(false);
  const [completed, setCompleted] = useState(false);
  const tapTimesRef = useRef<number[]>([]);
  const resetTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const settleTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const burstHideTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const wasPastTriggerRef = useRef(false);
  const shake = useRef(new Animated.Value(0)).current;

  const visible =
    enabled &&
    isActive &&
    isStarted &&
    !completed &&
    currentTime >= triggerTimeSec &&
    currentTime <= triggerTimeSec + promptDurationSec;

  const clearTimers = useCallback(() => {
    if (resetTimeoutRef.current) {
      clearTimeout(resetTimeoutRef.current);
      resetTimeoutRef.current = undefined;
    }
    if (settleTimeoutRef.current) {
      clearTimeout(settleTimeoutRef.current);
      settleTimeoutRef.current = undefined;
    }
    if (burstHideTimeoutRef.current) {
      clearTimeout(burstHideTimeoutRef.current);
      burstHideTimeoutRef.current = undefined;
    }
  }, []);

  const reset = useCallback(() => {
    clearTimers();
    tapTimesRef.current = [];
    wasPastTriggerRef.current = false;
    setTapCount(0);
    setBurstCount(0);
    setIsBurstLayerVisible(false);
    setCompleted(false);
    shake.stopAnimation();
    shake.setValue(0);
  }, [clearTimers, shake]);

  useEffect(() => reset, [reset]);

  useEffect(() => {
    reset();
  }, [reset, resetKey]);

  useEffect(() => {
    if (!enabled || !isActive || !isStarted) {
      reset();
      return;
    }
    const isPastTrigger = currentTime >= triggerTimeSec;
    if (!isPastTrigger && wasPastTriggerRef.current) {
      reset();
    }
    wasPastTriggerRef.current = isPastTrigger;
  }, [currentTime, enabled, isActive, isStarted, reset, triggerTimeSec]);

  const triggerBurst = useCallback(() => {
    if (burstHideTimeoutRef.current) {
      clearTimeout(burstHideTimeoutRef.current);
      burstHideTimeoutRef.current = undefined;
    }
    setIsBurstLayerVisible(true);
    setBurstVersion((version) => version + 1);
    shake.stopAnimation();
    shake.setValue(0);
    Animated.sequence([
      Animated.timing(shake, { toValue: 1, duration: 42, useNativeDriver: true }),
      Animated.timing(shake, { toValue: -1, duration: 42, useNativeDriver: true }),
      Animated.timing(shake, { toValue: 1, duration: 38, useNativeDriver: true }),
      Animated.timing(shake, { toValue: -1, duration: 38, useNativeDriver: true }),
      Animated.timing(shake, { toValue: 0, duration: 46, useNativeDriver: true })
    ]).start();
    burstHideTimeoutRef.current = setTimeout(() => {
      setIsBurstLayerVisible(false);
      burstHideTimeoutRef.current = undefined;
    }, BURST_LAYER_LIFETIME_MS);
  }, [shake]);

  const registerRapidTap = useCallback(() => {
    const now = Date.now();
    const recentTapTimes = [...tapTimesRef.current.filter((time) => now - time <= RAPID_TAP_WINDOW_MS), now];
    tapTimesRef.current = recentTapTimes;
    setTapCount(recentTapTimes.length);
    setBurstCount(recentTapTimes.length);
    triggerBurst();

    if (resetTimeoutRef.current) {
      clearTimeout(resetTimeoutRef.current);
    }
    if (settleTimeoutRef.current) {
      clearTimeout(settleTimeoutRef.current);
    }

    resetTimeoutRef.current = setTimeout(() => {
      tapTimesRef.current = [];
      setTapCount(0);
      setBurstCount(0);
      resetTimeoutRef.current = undefined;
    }, RAPID_TAP_WINDOW_MS);

    settleTimeoutRef.current = setTimeout(() => {
      tapTimesRef.current = [];
      setTapCount(0);
      setBurstCount(0);
      setCompleted(true);
      settleTimeoutRef.current = undefined;
    }, BURST_SETTLE_MS);
  }, [triggerBurst]);

  const handlePress = useCallback(() => {
    if (!visible) {
      return;
    }
    registerRapidTap();
  }, [registerRapidTap, visible]);

  const shakeTranslateX = shake.interpolate({
    inputRange: [-1, 0, 1],
    outputRange: [-8, 0, 8]
  });

  if (!enabled || !isActive || !isStarted) {
    return null;
  }

  if (!visible && !isBurstLayerVisible) {
    return null;
  }

  return (
    <>
      {visible ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="连续点击花朵互动"
          style={styles.promptTapTarget}
          onPress={handlePress}
        />
      ) : null}
      <Animated.View pointerEvents="none" style={[styles.feedbackLayer, { transform: [{ translateX: shakeTranslateX }] }]}>
        <RapidTapSurprise
          visible={visible}
          showBurst={isBurstLayerVisible}
          tapCount={tapCount}
          burstCount={burstCount}
          burstVersion={burstVersion}
        />
      </Animated.View>
    </>
  );
}

const styles = StyleSheet.create({
  promptTapTarget: {
    position: "absolute",
    right: 8,
    bottom: 540,
    width: 100,
    height: 100,
    borderRadius: 50,
    zIndex: 30
  },
  feedbackLayer: {
    ...StyleSheet.absoluteFillObject
  }
});

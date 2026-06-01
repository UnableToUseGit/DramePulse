import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as Haptics from "expo-haptics";
import { GestureResponderEvent, Pressable, StyleSheet } from "react-native";
import { EMOTION_AURA_CUES } from "./cues";
import { EmotionAuraLayer } from "./EmotionAuraLayer";
import {
  findActiveEmotionAuraCue,
  getSettlingEmotionAuraCue,
  getVisibleEmotionAuraCue,
  shouldResetEmotionAuraCue,
  shouldTimeoutEmotionAuraCue
} from "./scheduler";
import {
  createInitialTapGestureState,
  canAutoDismissEmotionAura,
  getEmotionEnergyLevel,
  getEmotionHapticFeedback,
  isEmotionExpressionVisible,
  reduceTapGesture,
  TAP_SETTLE_DELAY_MS,
  TAP_SINGLE_DELAY_MS,
  TapGestureState
} from "./tapGesture";
import type { EmotionAuraCue } from "./types";

const SETTLED_DISMISS_MS = 1400;

export function EmotionAuraExample({
  currentTime,
  isActive,
  onDismiss,
  onTogglePlayback
}: {
  currentTime: number;
  isActive: boolean;
  onDismiss: () => void;
  onTogglePlayback: () => void;
}) {
  const [completedCueIds, setCompletedCueIds] = useState<Set<string>>(() => new Set());
  const [tapState, setTapState] = useState<TapGestureState>(() => createInitialTapGestureState());
  const [engagedCue, setEngagedCue] = useState<EmotionAuraCue | undefined>();
  const [settledCue, setSettledCue] = useState<EmotionAuraCue | undefined>();
  const [lastTapPoint, setLastTapPoint] = useState<{ x: number; y: number } | undefined>();
  const previousTimeRef = useRef(currentTime);
  const activeCue = useMemo(
    () => findActiveEmotionAuraCue({ cues: EMOTION_AURA_CUES, currentTime, completedCueIds }),
    [completedCueIds, currentTime]
  );
  const cue = getVisibleEmotionAuraCue({ activeCue, engagedCue, settledCue });
  const tapStateRef = useRef(tapState);
  const activeCueRef = useRef(activeCue);
  const engagedCueRef = useRef(engagedCue);
  const tapTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    tapStateRef.current = tapState;
  }, [tapState]);

  useEffect(() => {
    activeCueRef.current = activeCue;
  }, [activeCue]);

  useEffect(() => {
    engagedCueRef.current = engagedCue;
  }, [engagedCue]);

  const clearTapTimer = useCallback(() => {
    if (tapTimerRef.current !== undefined) {
      clearTimeout(tapTimerRef.current);
      tapTimerRef.current = undefined;
    }
  }, []);

  const applyTapState = useCallback(
    (nextState: TapGestureState) => {
      tapStateRef.current = nextState;
      setTapState(nextState);
      if (nextState.action === "toggle_playback") {
        onTogglePlayback();
      }
      const hapticFeedback = getEmotionHapticFeedback(nextState.action);
      if (hapticFeedback === "selection") {
        void Haptics.selectionAsync();
      }
      const cueToSettle = getSettlingEmotionAuraCue({
        activeCue: activeCueRef.current,
        engagedCue: engagedCueRef.current
      });
      if (nextState.action === "settle_emotion" && cueToSettle) {
        setSettledCue(cueToSettle);
        setEngagedCue(undefined);
        engagedCueRef.current = undefined;
        setCompletedCueIds((ids) => new Set(ids).add(cueToSettle.cueId));
        clearTapTimer();
        dismissTimerRef.current = setTimeout(() => {
          setSettledCue(undefined);
          setTapState(createInitialTapGestureState());
          onDismiss();
        }, SETTLED_DISMISS_MS);
      }
    },
    [clearTapTimer, onDismiss, onTogglePlayback]
  );

  const scheduleDeadline = useCallback(
    (state: TapGestureState) => {
      clearTapTimer();
      if (state.nextDeadlineMs === undefined || state.phase === "settled") {
        return;
      }
      const delay = state.phase === "tap_pending" ? TAP_SINGLE_DELAY_MS : TAP_SETTLE_DELAY_MS;
      tapTimerRef.current = setTimeout(() => {
        applyTapState(reduceTapGesture(tapStateRef.current, { type: "time", nowMs: Date.now() }));
      }, delay);
    },
    [applyTapState, clearTapTimer]
  );

  const handlePress = useCallback((event: GestureResponderEvent) => {
    if (!isActive || !cue || settledCue) {
      return;
    }
    const nextState = reduceTapGesture(tapStateRef.current, { type: "tap", nowMs: Date.now() });
    if (isEmotionExpressionVisible(nextState)) {
      setLastTapPoint({
        x: event.nativeEvent.locationX,
        y: event.nativeEvent.locationY
      });
    }
    if (nextState.action === "start_emotion" && cue) {
      setEngagedCue(cue);
      engagedCueRef.current = cue;
    }
    applyTapState(nextState);
    scheduleDeadline(nextState);
  }, [applyTapState, cue, isActive, scheduleDeadline, settledCue]);

  useEffect(() => {
    const previousTime = previousTimeRef.current;
    previousTimeRef.current = currentTime;
    const resetCue = EMOTION_AURA_CUES.find((item) =>
      shouldResetEmotionAuraCue({ cue: item, previousTime, currentTime })
    );
    if (resetCue) {
      setCompletedCueIds((ids) => {
        const nextIds = new Set(ids);
        nextIds.delete(resetCue.cueId);
        return nextIds;
      });
      setTapState(createInitialTapGestureState());
      setEngagedCue(undefined);
      engagedCueRef.current = undefined;
      setSettledCue(undefined);
      setLastTapPoint(undefined);
      clearTapTimer();
    }
  }, [clearTapTimer, currentTime]);

  useEffect(() => {
    if (
      activeCue &&
      !engagedCue &&
      shouldTimeoutEmotionAuraCue({ cue: activeCue, currentTime }) &&
      canAutoDismissEmotionAura(tapState)
    ) {
      setCompletedCueIds((ids) => new Set(ids).add(activeCue.cueId));
      onDismiss();
    }
  }, [activeCue, currentTime, engagedCue, onDismiss, tapState.phase]);

  useEffect(
    () => () => {
      clearTapTimer();
      if (dismissTimerRef.current !== undefined) {
        clearTimeout(dismissTimerRef.current);
      }
    },
    [clearTapTimer]
  );

  if (!cue) {
    return null;
  }

  return (
    <Pressable accessibilityRole="button" accessibilityLabel={cue.label} onPress={handlePress} style={styles.root}>
      <EmotionAuraLayer
        cue={cue}
        tapCount={tapState.tapCount}
        energyLevel={getEmotionEnergyLevel(tapState.tapCount)}
        isSettled={settledCue !== undefined}
        lastTapPoint={lastTapPoint}
        showExpression={isEmotionExpressionVisible(tapState)}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    bottom: 74,
    zIndex: 8
  }
});

import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Animated, StyleSheet, View } from "react-native";
import {
  createHiddenPresenceState,
  reducePresenceState,
  ResonancePresenceState
} from "./presence";

const ENTER_DURATION_MS = 260;
const EXIT_DURATION_MS = 220;
const OFFSCREEN_X = 76;

export function ActionRailResonanceSlot({
  cueId,
  children
}: {
  cueId?: string;
  children: ReactNode;
}) {
  const [presence, setPresence] = useState<ResonancePresenceState>(() => createHiddenPresenceState());
  const translateX = useRef(new Animated.Value(OFFSCREEN_X)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const shouldRender = presence.phase !== "hidden";
  const content = useMemo(() => (shouldRender ? children : null), [children, shouldRender]);

  useEffect(() => {
    setPresence((state) =>
      reducePresenceState(state, cueId ? { type: "cue_present", cueId } : { type: "cue_absent" })
    );
  }, [cueId]);

  useEffect(() => {
    if (presence.phase === "entering") {
      translateX.setValue(OFFSCREEN_X);
      opacity.setValue(0);
      Animated.parallel([
        Animated.timing(translateX, {
          toValue: 0,
          duration: ENTER_DURATION_MS,
          useNativeDriver: true
        }),
        Animated.timing(opacity, {
          toValue: 1,
          duration: ENTER_DURATION_MS,
          useNativeDriver: true
        })
      ]).start(() => {
        setPresence((state) => reducePresenceState(state, { type: "enter_complete" }));
      });
      return;
    }

    if (presence.phase === "exiting") {
      Animated.parallel([
        Animated.timing(translateX, {
          toValue: OFFSCREEN_X,
          duration: EXIT_DURATION_MS,
          useNativeDriver: true
        }),
        Animated.timing(opacity, {
          toValue: 0,
          duration: EXIT_DURATION_MS,
          useNativeDriver: true
        })
      ]).start(() => {
        setPresence((state) => reducePresenceState(state, { type: "exit_complete" }));
      });
    }
  }, [opacity, presence.phase, translateX]);

  if (!shouldRender) {
    return null;
  }

  return (
    <View style={styles.slot} pointerEvents={cueId ? "auto" : "none"}>
      <Animated.View style={[styles.animated, { opacity, transform: [{ translateX }] }]}>{content}</Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  slot: {
    width: 58,
    overflow: "visible"
  },
  animated: {
    alignItems: "center"
  }
});

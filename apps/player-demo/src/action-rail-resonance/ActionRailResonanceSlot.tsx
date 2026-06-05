import { ReactNode, useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, View } from "react-native";
import {
  createHiddenPresenceState,
  reducePresenceState,
  ResonancePresenceState
} from "./presence";

const ENTER_DURATION_MS = 260;
const EXIT_DURATION_MS = 560;
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
  const shouldShowAnimatedContent = presence.phase !== "hidden";
  const [renderedChildren, setRenderedChildren] = useState<ReactNode>(null);

  useEffect(() => {
    setPresence((state) =>
      reducePresenceState(state, cueId ? { type: "cue_present", cueId } : { type: "cue_absent" })
    );
  }, [cueId]);

  useEffect(() => {
    if (cueId) {
      setRenderedChildren(children);
    }
  }, [children, cueId]);

  useEffect(() => {
    if (presence.phase === "hidden") {
      setRenderedChildren(null);
    }
  }, [presence.phase]);

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

  return (
    <View style={styles.slot} pointerEvents={cueId ? "auto" : "none"}>
      {shouldShowAnimatedContent ? (
        <Animated.View style={[styles.animated, { opacity, transform: [{ translateX }] }]}>
          {renderedChildren}
        </Animated.View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  slot: {
    width: 58,
    height: 58,
    overflow: "visible"
  },
  animated: {
    alignItems: "center"
  }
});

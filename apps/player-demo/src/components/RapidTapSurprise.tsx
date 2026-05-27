import { Ionicons } from "@expo/vector-icons";
import { useEffect, useMemo, useRef } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import { colors } from "../theme";

const STICKER_TEXTS = ["女主很可爱", "女主太棒了", "磕到了", "这段好甜"];
const STICKER_COUNT = 18;

function buildStickerLayout() {
  return Array.from({ length: STICKER_COUNT }).map((_, index) => {
    const column = index % 3;
    const row = Math.floor(index / 3);
    return {
      id: `sticker-${index}`,
      text: STICKER_TEXTS[index % STICKER_TEXTS.length],
      left: 18 + column * 27 + (row % 2) * 6,
      top: 82 + row * 34,
      delay: index * 20,
      drift: (column - 1) * 28
    };
  });
}

export function RapidTapSurprise({
  visible,
  showBurst,
  tapCount,
  burstCount,
  burstVersion
}: {
  visible: boolean;
  showBurst: boolean;
  tapCount: number;
  burstCount: number;
  burstVersion: number;
}) {
  const burst = useRef(new Animated.Value(0)).current;
  const promptPulse = useRef(new Animated.Value(0)).current;
  const stickers = useMemo(buildStickerLayout, []);

  useEffect(() => {
    if (!visible) {
      promptPulse.stopAnimation();
      promptPulse.setValue(0);
      return;
    }

    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(promptPulse, {
          toValue: 1,
          duration: 880,
          useNativeDriver: true
        }),
        Animated.timing(promptPulse, {
          toValue: 0,
          duration: 880,
          useNativeDriver: true
        })
      ])
    );
    animation.start();
    return () => {
      animation.stop();
    };
  }, [promptPulse, visible]);

  useEffect(() => {
    if (burstVersion <= 0) {
      return;
    }
    burst.setValue(0);
    const animation = Animated.timing(burst, {
      toValue: 1,
      duration: 780,
      useNativeDriver: true
    });
    animation.start();
    return () => {
      animation.stop();
    };
  }, [burst, burstVersion]);

  const burstOpacity = burst.interpolate({
    inputRange: [0, 0.08, 0.78, 1],
    outputRange: [0, 1, 1, 0]
  });
  const promptScale = promptPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.96, 1.06]
  });
  const haloScale = promptPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.92, 1.28]
  });
  const haloOpacity = promptPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.1, 0.46]
  });
  const flowerOpacity = promptPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.62, 0.96]
  });

  return (
    <View pointerEvents="none" style={styles.root}>
      {visible ? (
        <View style={styles.prompt}>
          <Animated.View
            style={[styles.promptHalo, { opacity: haloOpacity, transform: [{ scale: haloScale }] }]}
          />
          <Animated.View style={[styles.promptGlass, { transform: [{ scale: promptScale }] }]}>
            <Animated.View style={{ opacity: flowerOpacity }}>
              <Ionicons name="flower-outline" size={45} color="rgba(255, 231, 237, 0.98)" />
            </Animated.View>
          </Animated.View>
          {tapCount > 1 ? (
            <View style={styles.tapCountBadge}>
              <Text style={styles.tapCount}>x{tapCount}</Text>
            </View>
          ) : null}
        </View>
      ) : null}
      {showBurst && burstVersion > 0 ? (
        <Animated.View style={[styles.burstLayer, { opacity: burstOpacity }]}>
          <Animated.View
            style={[
              styles.comboSticker,
              {
                transform: [
                  {
                    scale: burst.interpolate({
                      inputRange: [0, 0.16, 0.72, 1],
                      outputRange: [0.4, 1.18, 1, 0.82]
                    })
                  },
                  {
                    translateY: burst.interpolate({
                      inputRange: [0, 0.72, 1],
                      outputRange: [20, -10, -22]
                    })
                  }
                ]
              }
            ]}
          >
            <Text style={styles.comboText}>x{Math.max(1, burstCount)}</Text>
            <Text style={styles.comboEmoji}>🤩😂</Text>
          </Animated.View>
          {stickers.map((sticker) => (
            <Animated.Text
              key={sticker.id}
              style={[
                styles.flyingText,
                {
                  left: `${sticker.left}%`,
                  top: sticker.top,
                  opacity: burst.interpolate({
                    inputRange: [0, 0.12, 0.78, 1],
                    outputRange: [0, 0.9, 0.72, 0]
                  }),
                  transform: [
                    {
                      translateX: burst.interpolate({
                        inputRange: [0, 1],
                        outputRange: [0, sticker.drift]
                      })
                    },
                    {
                      translateY: burst.interpolate({
                        inputRange: [0, 0.24, 1],
                        outputRange: [12, 0, -34 - sticker.delay / 10]
                      })
                    },
                    {
                      scale: burst.interpolate({
                        inputRange: [0, 0.18, 1],
                        outputRange: [0.78, 1, 0.92]
                      })
                    }
                  ]
                }
              ]}
            >
              {sticker.text}
            </Animated.Text>
          ))}
        </Animated.View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 12
  },
  prompt: {
    position: "absolute",
    right: 8,
    bottom: 540,
    width: 100,
    height: 100,
    alignItems: "center",
    justifyContent: "center"
  },
  promptHalo: {
    position: "absolute",
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: "rgba(255, 135, 169, 0.12)",
    borderWidth: 1,
    borderColor: "rgba(255, 218, 230, 0.72)"
  },
  promptGlass: {
    width: 64,
    height: 64,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 32,
    backgroundColor: "rgba(255, 255, 255, 0.1)",
    borderWidth: 1,
    borderColor: "rgba(255, 231, 237, 0.56)",
    shadowColor: "#FF90AE",
    shadowOpacity: 0.26,
    shadowRadius: 7,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2
  },
  tapCountBadge: {
    position: "absolute",
    right: 10,
    top: 11,
    minWidth: 24,
    height: 24,
    paddingHorizontal: 6,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: "rgba(255, 92, 130, 0.88)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.64)"
  },
  tapCount: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "800",
    textAlign: "center"
  },
  burstLayer: {
    ...StyleSheet.absoluteFillObject
  },
  comboSticker: {
    position: "absolute",
    alignSelf: "center",
    top: "45%",
    alignItems: "center"
  },
  comboText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900",
    textShadowColor: "rgba(0,0,0,0.55)",
    textShadowRadius: 4
  },
  comboEmoji: {
    marginTop: 2,
    fontSize: 34
  },
  flyingText: {
    position: "absolute",
    color: colors.text,
    fontSize: 12,
    fontWeight: "900",
    textShadowColor: "rgba(0,0,0,0.62)",
    textShadowRadius: 3
  }
});

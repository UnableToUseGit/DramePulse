import { useEffect, useRef, useState } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";
import { BrokenHeartGlyph } from "./BrokenHeartGlyph";
import { CandyResonanceIcon } from "./CandyResonanceIcon";
import { LaughResonanceGlyph } from "./LaughResonanceGlyph";
import { ThrillWordGlyph } from "./ThrillWordGlyph";
import { appendBurstToQueue } from "./burstQueue";
import { createCandyBurstSprites } from "./candyBurst";
import { createHeartbreakBurstSprites } from "./heartbreakBurst";
import { createLaughBurstSprites } from "./laughBurst";
import type { LaughBurstVariant } from "./laughBurst";
import type { ActionRailResonanceCue, ActionRailResonanceEmotionType } from "./types";

// const BURST_DURATION_MS = 960;
const BURST_DURATION_MS = 1200;
// const TOSS_PEAK_PROGRESS = 0.38;
const TOSS_PEAK_PROGRESS = 0.52;
const THRILL_DURATION_MS = 1800;
const LAUGH_DURATION_MS = 1200;
// const HEARTBREAK_DURATION_MS = 880;
const HEARTBREAK_DURATION_MS = 1200;

const EMOTION_BURST_COLORS: Record<ActionRailResonanceEmotionType, { primary: string; soft: string }> = {
  爽点: {
    primary: "rgba(255,106,26,0.9)",
    soft: "rgba(255,106,26,0.18)"
  },
  笑点: {
    primary: "rgba(255,209,102,0.92)",
    soft: "rgba(255,209,102,0.18)"
  },
  甜点: {
    primary: "rgba(255,123,189,0.9)",
    soft: "rgba(255,123,189,0.18)"
  },
  泪点: {
    primary: "rgba(137,200,255,0.92)",
    soft: "rgba(137,200,255,0.18)"
  }
};

type CandyBurst = {
  id: number;
  variant?: LaughBurstVariant;
};

function getBurstDurationMs(emotionType: ActionRailResonanceEmotionType) {
  if (emotionType === "爽点") {
    return THRILL_DURATION_MS;
  }
  if (emotionType === "笑点") {
    return LAUGH_DURATION_MS;
  }
  if (emotionType === "泪点") {
    return HEARTBREAK_DURATION_MS;
  }
  return BURST_DURATION_MS;
}

function ThrillBurstView({ burst }: { burst: CandyBurst }) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: THRILL_DURATION_MS,
      easing: Easing.linear,
      useNativeDriver: true
    }).start();
  }, [progress]);

  const wordOpacity = progress.interpolate({
    inputRange: [0, 0.03, 0.9, 1],
    outputRange: [0, 1, 1, 0]
  });
  const wordScale = progress.interpolate({
    inputRange: [0, 0.04, 0.16, 0.24, 1],
    outputRange: [0.18, 0.62, 1.22, 1.08, 1.02]
  });
  const wordTranslateY = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0]
  });
  const bangOpacity = progress.interpolate({
    inputRange: [0, 0.24, 0.245, 0.94, 1],
    outputRange: [0, 0, 1, 1, 0]
  });
  const bangTranslateX = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0]
  });
  const bangTranslateY = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0]
  });
  const bangScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1]
  });
  const bangRotate = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "0deg"]
  });

  return (
    <Animated.View style={styles.burst}>
      <Animated.View
        style={[
          styles.thrillMainWord,
          {
            opacity: wordOpacity,
            transform: [{ translateY: wordTranslateY }, { scale: wordScale }]
          }
        ]}
      >
        <ThrillWordGlyph size={104} />
      </Animated.View>
      <Animated.Text
        style={[
          styles.thrillBang,
          {
            opacity: bangOpacity,
            transform: [
              { translateX: bangTranslateX },
              { translateY: bangTranslateY },
              { scale: bangScale },
              { rotate: bangRotate }
            ]
          }
        ]}
      >
        !
      </Animated.Text>
    </Animated.View>
  );
}

function CandyBurstView({ burst }: { burst: CandyBurst }) {
  const progress = useRef(new Animated.Value(0)).current;
  const sprites = createCandyBurstSprites({ burstId: burst.id });

  useEffect(() => {
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: BURST_DURATION_MS,
      useNativeDriver: true
    }).start();
  }, [progress]);

  const opacity = progress.interpolate({
    inputRange: [0, 0.08, 0.9, 1],
    outputRange: [0, 1, 1, 0]
  });

  return (
    <Animated.View style={[styles.burst, { opacity }]}>
      {sprites.map((sprite) => {
        const start = sprite.delay / BURST_DURATION_MS;
        const peak = Math.min(start + TOSS_PEAK_PROGRESS, 0.72);
        const translateX = progress.interpolate({
          inputRange: [0, start, peak, 1],
          outputRange: [sprite.startX, sprite.startX, sprite.peakX, sprite.endX]
        });
        const translateY = progress.interpolate({
          inputRange: [0, start, peak, 1],
          outputRange: [sprite.startY, sprite.startY, sprite.peakY, sprite.endY]
        });
        const scale = progress.interpolate({
          inputRange: [0, start, peak, 1],
          outputRange: [0.82, 0.82, 1, 0.86]
        });
        const rotate = progress.interpolate({
          inputRange: [0, start, peak, 1],
          outputRange: [
            `${sprite.rotation * -0.18}deg`,
            `${sprite.rotation * -0.18}deg`,
            `${sprite.rotation * 0.56}deg`,
            `${sprite.rotation}deg`
          ]
        });

        return (
          <Animated.View
            key={sprite.id}
            style={[
              styles.candySprite,
              {
                width: sprite.size,
                height: sprite.size,
                transform: [{ translateX }, { translateY }, { scale }, { rotate }]
              }
            ]}
          >
            <CandyResonanceIcon isLit size={sprite.size} />
          </Animated.View>
        );
      })}
    </Animated.View>
  );
}

function LaughBurstView({ burst }: { burst: CandyBurst }) {
  const progress = useRef(new Animated.Value(0)).current;
  const sprites = createLaughBurstSprites({ burstId: burst.id, variant: burst.variant });

  useEffect(() => {
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: LAUGH_DURATION_MS,
      useNativeDriver: true
    }).start();
  }, [progress]);

  return (
    <Animated.View style={styles.burst}>
      {sprites.map((sprite) => {
        const start = Math.max(sprite.delay / LAUGH_DURATION_MS, 0.001);
        const reveal = Math.min(start + 0.12, 0.72);
        const fade = Math.min(start + 0.76, 0.94);
        const opacity = progress.interpolate({
          inputRange: [0, start, reveal, fade, 1],
          outputRange: [0, 0, 1, 1, 0]
        });
        const translateX = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [sprite.startX, sprite.startX, sprite.endX]
        });
        const translateY = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [sprite.startY, sprite.startY, sprite.endY]
        });
        const scale = progress.interpolate({
          inputRange: [0, start, reveal, 1],
          outputRange: [sprite.startScale, sprite.startScale, sprite.endScale, sprite.endScale * 1.08]
        });
        const rotate = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [`${sprite.rotation * -0.32}deg`, `${sprite.rotation * -0.32}deg`, `${sprite.rotation}deg`]
        });

        return (
          <Animated.View
            key={sprite.id}
            style={[
              styles.laughGlyph,
              {
                opacity,
                transform: [{ translateX }, { translateY }, { scale }, { rotate }]
              }
            ]}
          >
            <LaughResonanceGlyph size={34} />
          </Animated.View>
        );
      })}
    </Animated.View>
  );
}

function HeartbreakBurstView({ burst }: { burst: CandyBurst }) {
  const progress = useRef(new Animated.Value(0)).current;
  const sprites = createHeartbreakBurstSprites({ burstId: burst.id });

  useEffect(() => {
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: HEARTBREAK_DURATION_MS,
      useNativeDriver: true
    }).start();
  }, [progress]);

  return (
    <Animated.View style={styles.burst}>
      {sprites.map((sprite) => {
        const start = Math.max(sprite.delay / HEARTBREAK_DURATION_MS, 0.001);
        const reveal = Math.min(start + 0.14, 0.74);
        const fade = Math.min(start + 0.76, 0.94);
        const opacity = progress.interpolate({
          inputRange: [0, start, reveal, fade, 1],
          outputRange: [0, 0, 1, 0.82, 0]
        });
        const translateX = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [sprite.startX, sprite.startX, sprite.endX]
        });
        const translateY = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [sprite.startY, sprite.startY, sprite.endY]
        });
        const scale = progress.interpolate({
          inputRange: [0, start, reveal, 1],
          outputRange: [sprite.startScale, sprite.startScale, sprite.endScale, sprite.endScale * 0.82]
        });
        const rotate = progress.interpolate({
          inputRange: [0, start, 1],
          outputRange: [`${sprite.rotation * -0.28}deg`, `${sprite.rotation * -0.28}deg`, `${sprite.rotation}deg`]
        });

        return (
          <Animated.View
            key={sprite.id}
            style={[
              styles.heartbreakGlyph,
              {
                width: sprite.size,
                height: sprite.size,
                opacity,
                transform: [{ translateX }, { translateY }, { scale }, { rotate }]
              }
            ]}
          >
            <BrokenHeartGlyph size={sprite.size} />
          </Animated.View>
        );
      })}
    </Animated.View>
  );
}

function SimpleBurstView({ emotionType }: { emotionType: ActionRailResonanceEmotionType }) {
  const appear = useRef(new Animated.Value(0)).current;
  const ringScale = useRef(new Animated.Value(0.68)).current;
  const burstColors = EMOTION_BURST_COLORS[emotionType];

  useEffect(() => {
    appear.setValue(1);
    ringScale.setValue(0.68);
    Animated.parallel([
      Animated.timing(appear, {
        toValue: 0,
        duration: 620,
        useNativeDriver: true
      }),
      Animated.spring(ringScale, {
        toValue: 1.22,
        friction: 8,
        tension: 120,
        useNativeDriver: true
      })
    ]).start();
  }, [appear, ringScale]);

  return (
    <Animated.View
      style={[
        styles.simpleRing,
        {
          borderColor: burstColors.primary,
          backgroundColor: burstColors.soft,
          opacity: appear,
          transform: [{ scale: ringScale }]
        }
      ]}
    />
  );
}

export function ActionRailResonanceBurstLayer({
  cue,
  tapCount
}: {
  cue?: ActionRailResonanceCue;
  tapCount: number;
  releaseCount: number;
}) {
  const [bursts, setBursts] = useState<CandyBurst[]>([]);
  const previousTapCount = useRef(0);
  const nextBurstId = useRef(0);
  const cleanupTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    return () => {
      cleanupTimers.current.forEach(clearTimeout);
      cleanupTimers.current = [];
    };
  }, []);

  useEffect(() => {
    if (!cue || tapCount <= 0) {
      previousTapCount.current = 0;
      setBursts([]);
      cleanupTimers.current.forEach(clearTimeout);
      cleanupTimers.current = [];
      return;
    }
    if (tapCount <= previousTapCount.current) {
      return;
    }

    previousTapCount.current = tapCount;
    nextBurstId.current += 1;
    const burstId = nextBurstId.current;
    setBursts((currentBursts) => {
      const variant = cue.emotionType === "笑点" && currentBursts.length > 0 ? "combo" : "full";
      return appendBurstToQueue(currentBursts, { id: burstId, variant });
    });

    const timeoutId = setTimeout(() => {
      setBursts((currentBursts) => currentBursts.filter((burst) => burst.id !== burstId));
      cleanupTimers.current = cleanupTimers.current.filter((timer) => timer !== timeoutId);
    }, getBurstDurationMs(cue.emotionType) + 80);
    cleanupTimers.current.push(timeoutId);
  }, [cue, tapCount]);

  if (!cue || tapCount <= 0) {
    return null;
  }

  return (
    <View pointerEvents="none" style={styles.root}>
      {bursts.map((burst) => (
        cue.emotionType === "爽点" ? (
          <ThrillBurstView key={burst.id} burst={burst} />
        ) : cue.emotionType === "甜点" ? (
          <CandyBurstView key={burst.id} burst={burst} />
        ) : cue.emotionType === "笑点" ? (
          <LaughBurstView key={burst.id} burst={burst} />
        ) : cue.emotionType === "泪点" ? (
          <HeartbreakBurstView key={burst.id} burst={burst} />
        ) : (
          <SimpleBurstView key={burst.id} emotionType={cue.emotionType} />
        )
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 9
  },
  burst: {
    position: "absolute",
    width: 1,
    height: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  candySprite: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center"
  },
  thrillMainWord: {
    position: "absolute",
    left: -52,
    top: -52,
    width: 104,
    height: 104,
    alignItems: "center",
    justifyContent: "center"
  },
  thrillBang: {
    position: "absolute",
    left: 43,
    top: -52,
    width: 42,
    height: 92,
    color: "#ffd166",
    fontSize: 84,
    fontWeight: "900",
    lineHeight: 92,
    textAlign: "center",
    textShadowColor: "rgba(179,52,8,0.72)",
    textShadowRadius: 7
  },
  laughGlyph: {
    position: "absolute",
    width: 34,
    height: 34,
    alignItems: "center",
    justifyContent: "center"
  },
  heartbreakGlyph: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center"
  },
  simpleRing: {
    position: "absolute",
    width: 132,
    height: 132,
    borderRadius: 66,
    borderWidth: 2
  }
});

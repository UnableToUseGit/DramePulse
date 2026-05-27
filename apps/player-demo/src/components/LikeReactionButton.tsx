import { Ionicons } from "@expo/vector-icons";
import { useEffect, useMemo, useRef, useState } from "react";
import { Animated, Dimensions, PanResponder, StyleSheet, Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { colors, radii, spacing } from "../theme";

const HOLD_DURATION_MS = 1000;
const PROGRESS_RADIUS = 27;
const PROGRESS_CIRCUMFERENCE = 2 * Math.PI * PROGRESS_RADIUS;
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

type ReactionOption = {
  id: string;
  emoji: string;
  label: string;
};

const REACTIONS: ReactionOption[] = [
  { id: "kswl", emoji: "🤩", label: "kswl" },
  { id: "niu", emoji: "👍", label: "牛" },
  { id: "love", emoji: "❤️", label: "爱了" },
  { id: "shock", emoji: "😮", label: "惊呆" }
];

const MENU_ITEM_HEIGHT = 46;

export function LikeReactionButton({ count }: { count: string }) {
  const [liked, setLiked] = useState(false);
  const [isHolding, setIsHolding] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [activeReactionId, setActiveReactionId] = useState<string | undefined>();
  const [burstReaction, setBurstReaction] = useState<ReactionOption | undefined>();
  const holdCompletedRef = useRef(false);
  const pressStartYRef = useRef(0);
  const charge = useRef(new Animated.Value(0)).current;
  const burst = useRef(new Animated.Value(0)).current;
  const windowSize = Dimensions.get("window");

  const activeReaction = useMemo(
    () => REACTIONS.find((reaction) => reaction.id === activeReactionId),
    [activeReactionId]
  );

  useEffect(() => {
    return () => {
      charge.stopAnimation();
      burst.stopAnimation();
    };
  }, [burst, charge]);

  const resetHold = () => {
    charge.stopAnimation();
    charge.setValue(0);
    setIsHolding(false);
    setMenuVisible(false);
    setActiveReactionId(undefined);
    holdCompletedRef.current = false;
  };

  const playBurst = (reaction: ReactionOption) => {
    setLiked(true);
    setBurstReaction(reaction);
    burst.setValue(0);
    Animated.timing(burst, {
      toValue: 1,
      duration: 920,
      useNativeDriver: true
    }).start(() => {
      setBurstReaction(undefined);
      burst.setValue(0);
    });
  };

  const getReactionFromTouch = (moveY: number) => {
    const menuTopY = pressStartYRef.current - MENU_ITEM_HEIGHT * 3.3;
    const index = Math.min(Math.max(Math.floor((moveY - menuTopY) / MENU_ITEM_HEIGHT), 0), REACTIONS.length - 1);
    return REACTIONS[index];
  };

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (event) => {
          pressStartYRef.current = event.nativeEvent.pageY;
          holdCompletedRef.current = false;
          setIsHolding(true);
          setMenuVisible(false);
          setActiveReactionId(undefined);
          charge.setValue(0);
          Animated.timing(charge, {
            toValue: 1,
            duration: HOLD_DURATION_MS,
            useNativeDriver: false
          }).start(({ finished }) => {
            if (!finished) {
              return;
            }
            holdCompletedRef.current = true;
            setMenuVisible(true);
            setActiveReactionId(REACTIONS[0].id);
          });
        },
        onPanResponderMove: (_, gestureState) => {
          if (!holdCompletedRef.current) {
            return;
          }
          setActiveReactionId(getReactionFromTouch(gestureState.moveY).id);
        },
        onPanResponderRelease: (_, gestureState) => {
          if (holdCompletedRef.current) {
            playBurst(activeReaction ?? getReactionFromTouch(gestureState.moveY));
          } else {
            setLiked((current) => !current);
          }
          resetHold();
        },
        onPanResponderTerminate: () => {
          resetHold();
        }
      }),
    [activeReaction, charge]
  );

  const progressOffset = charge.interpolate({
    inputRange: [0, 1],
    outputRange: [PROGRESS_CIRCUMFERENCE, 0]
  });
  const holdScale = charge.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.08]
  });
  const burstOpacity = burst.interpolate({
    inputRange: [0, 0.08, 0.7, 1],
    outputRange: [0, 1, 0.9, 0]
  });
  const rippleScale = burst.interpolate({
    inputRange: [0, 0.16, 1],
    outputRange: [0.22, 1.55, 4.8]
  });
  const rippleOpacity = burst.interpolate({
    inputRange: [0, 0.12, 0.45, 1],
    outputRange: [0, 0.72, 0.26, 0]
  });

  return (
    <View style={styles.root}>
      {burstReaction ? (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.burstLayer,
            {
              width: windowSize.width,
              height: windowSize.height,
              right: -spacing.md,
              bottom: -158,
              opacity: burstOpacity
            }
          ]}
        >
          <Animated.View
            style={[
              styles.ripple,
              {
                opacity: rippleOpacity,
                transform: [{ scale: rippleScale }]
              }
            ]}
          />
          <Animated.View
            style={[
              styles.rippleSecondary,
              {
                opacity: burst.interpolate({
                  inputRange: [0, 0.18, 0.56, 1],
                  outputRange: [0, 0.48, 0.18, 0]
                }),
                transform: [
                  {
                    scale: burst.interpolate({
                      inputRange: [0, 0.22, 1],
                      outputRange: [0.12, 1.1, 3.6]
                    })
                  }
                ]
              }
            ]}
          />
          {Array.from({ length: 58 }).map((_, index) => {
            const cluster = index % 3;
            const angle = -Math.PI / 2 + ((index % 18) - 8.5) * 0.15 + (cluster - 1) * 0.12;
            const distance = 210 + (index % 8) * 34 + cluster * 24;
            const driftX = Math.cos(angle) * distance + ((index % 2 === 0 ? 1 : -1) * (20 + (index % 5) * 7));
            const launchY = Math.sin(angle) * distance - 126 - (index % 5) * 20;
            const settleY = launchY + 30 + (index % 3) * 10;
            return (
              <Animated.Text
                key={index}
                style={[
                  styles.burstEmoji,
                  {
                    transform: [
                      {
                        translateX: burst.interpolate({
                          inputRange: [0, 0.18, 1],
                          outputRange: [0, driftX * 0.18, driftX]
                        })
                      },
                      {
                        translateY: burst.interpolate({
                          inputRange: [0, 0.18, 0.78, 1],
                          outputRange: [0, launchY * 0.28, launchY, settleY]
                        })
                      },
                      {
                        scale: burst.interpolate({
                          inputRange: [0, 0.1, 0.28, 1],
                          outputRange: [0.3, 1.56, 1.18, 0.82]
                        })
                      },
                      {
                        rotate: burst.interpolate({
                          inputRange: [0, 1],
                          outputRange: ["0deg", `${index % 2 === 0 ? 18 : -18}deg`]
                        })
                      }
                    ]
                  }
                ]}
              >
                {burstReaction.emoji}
              </Animated.Text>
            );
          })}
          {Array.from({ length: 26 }).map((_, index) => {
            const angle = -Math.PI / 2 + ((index % 13) - 6) * 0.22;
            const distance = 150 + (index % 6) * 34;
            const driftX = Math.cos(angle) * distance;
            const launchY = Math.sin(angle) * distance - 74;
            return (
              <Animated.View
                key={`particle-${index}`}
                style={[
                  styles.particle,
                  {
                    transform: [
                      {
                        translateX: burst.interpolate({
                          inputRange: [0, 0.16, 1],
                          outputRange: [0, driftX * 0.12, driftX]
                        })
                      },
                      {
                        translateY: burst.interpolate({
                          inputRange: [0, 0.16, 0.78, 1],
                          outputRange: [0, launchY * 0.22, launchY, launchY + 36]
                        })
                      },
                      {
                        scale: burst.interpolate({
                          inputRange: [0, 0.16, 0.62, 1],
                          outputRange: [0.2, 1.25, 0.9, 0]
                        })
                      }
                    ]
                  }
                ]}
              />
            );
          })}
        </Animated.View>
      ) : null}

      {menuVisible ? (
        <View style={styles.menu} pointerEvents="none">
          {REACTIONS.map((reaction) => {
            const selected = activeReactionId === reaction.id;
            return (
              <View key={reaction.id} style={[styles.menuItem, selected ? styles.menuItemActive : null]}>
                <Text style={styles.menuEmoji}>{reaction.emoji}</Text>
                <Text style={[styles.menuText, selected ? styles.menuTextActive : null]}>{reaction.label}</Text>
              </View>
            );
          })}
        </View>
      ) : null}

      <View style={styles.touchTarget} {...panResponder.panHandlers}>
        <Animated.View style={[styles.iconWrap, isHolding ? { transform: [{ scale: holdScale }] } : null]}>
          {isHolding ? (
            <Svg width={72} height={72} style={styles.progressSvg} viewBox="0 0 72 72">
              <Circle
                cx={36}
                cy={36}
                r={PROGRESS_RADIUS}
                stroke="rgba(255,255,255,0.22)"
                strokeWidth={4}
                fill="transparent"
              />
              <AnimatedCircle
                cx={36}
                cy={36}
                r={PROGRESS_RADIUS}
                stroke="#FF4D6D"
                strokeWidth={4}
                fill="transparent"
                strokeLinecap="round"
                strokeDasharray={`${PROGRESS_CIRCUMFERENCE} ${PROGRESS_CIRCUMFERENCE}`}
                strokeDashoffset={progressOffset}
                transform="rotate(-90 36 36)"
              />
            </Svg>
          ) : null}
          <Ionicons name="heart" size={42} color={liked ? "#FF335F" : "#fff"} />
        </Animated.View>
        <Text style={styles.railText}>{count}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "relative",
    alignItems: "center",
    gap: spacing.xs,
    zIndex: 18
  },
  touchTarget: {
    alignItems: "center",
    width: 76,
    gap: spacing.xs
  },
  iconWrap: {
    width: 72,
    height: 72,
    alignItems: "center",
    justifyContent: "center"
  },
  progressSvg: {
    position: "absolute"
  },
  railText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    textShadowColor: "rgba(0,0,0,0.68)",
    textShadowRadius: 4
  },
  menu: {
    position: "absolute",
    right: 72,
    bottom: 24,
    gap: spacing.xs
  },
  menuItem: {
    width: 92,
    height: MENU_ITEM_HEIGHT - 4,
    paddingHorizontal: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: "rgba(0,0,0,0.62)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)"
  },
  menuItemActive: {
    backgroundColor: "rgba(255,77,109,0.9)",
    borderColor: "rgba(255,255,255,0.76)"
  },
  menuEmoji: {
    fontSize: 18
  },
  menuText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "900"
  },
  menuTextActive: {
    color: "#fff"
  },
  burstLayer: {
    position: "absolute",
    overflow: "visible"
  },
  ripple: {
    position: "absolute",
    left: "50%",
    bottom: 34,
    width: 92,
    height: 92,
    marginLeft: -46,
    borderRadius: 46,
    borderWidth: 2,
    borderColor: "rgba(255,77,109,0.72)",
    backgroundColor: "rgba(255,77,109,0.1)"
  },
  rippleSecondary: {
    position: "absolute",
    left: "50%",
    bottom: 34,
    width: 62,
    height: 62,
    marginLeft: -31,
    borderRadius: 31,
    borderWidth: 1,
    borderColor: "rgba(255,213,138,0.62)",
    backgroundColor: "rgba(255,213,138,0.08)"
  },
  burstEmoji: {
    position: "absolute",
    left: "50%",
    bottom: 52,
    marginLeft: -15,
    fontSize: 31
  },
  particle: {
    position: "absolute",
    left: "50%",
    bottom: 74,
    width: 7,
    height: 7,
    marginLeft: -3.5,
    borderRadius: 4,
    backgroundColor: "rgba(255,213,138,0.92)"
  }
});

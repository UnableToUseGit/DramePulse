import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Animated, Modal, PanResponder, Pressable, StyleSheet, Text, View } from "react-native";
import type { RoleCommerceFeedAd } from "../domain/roleCommerceAds";
import { colors, radii, spacing } from "../theme";

const SHEET_HIDDEN_TRANSLATE_Y = 340;
const SWIPE_DISMISS_DISTANCE_PX = 72;
const SWIPE_DISMISS_VELOCITY = 0.72;

export function RoleCommerceProductSheet({
  visible,
  ad,
  onClose
}: {
  visible: boolean;
  ad: RoleCommerceFeedAd;
  onClose: () => void;
}) {
  const [shouldRender, setShouldRender] = useState(visible);
  const backdropOpacity = useRef(new Animated.Value(visible ? 1 : 0)).current;
  const sheetTranslateY = useRef(new Animated.Value(visible ? 0 : SHEET_HIDDEN_TRANSLATE_Y)).current;

  const closeWithSheetAnimation = useCallback(() => {
    if (!visible) {
      return;
    }
    Animated.parallel([
      Animated.timing(backdropOpacity, {
        toValue: 0,
        duration: 160,
        useNativeDriver: true
      }),
      Animated.timing(sheetTranslateY, {
        toValue: SHEET_HIDDEN_TRANSLATE_Y,
        duration: 200,
        useNativeDriver: true
      })
    ]).start(({ finished }) => {
      if (finished) {
        onClose();
        setShouldRender(false);
        requestAnimationFrame(() => {
          backdropOpacity.setValue(0);
          sheetTranslateY.setValue(SHEET_HIDDEN_TRANSLATE_Y);
        });
      }
    });
  }, [backdropOpacity, onClose, sheetTranslateY, visible]);

  useEffect(() => {
    if (visible) {
      setShouldRender(true);
      sheetTranslateY.setValue(SHEET_HIDDEN_TRANSLATE_Y);
      Animated.parallel([
        Animated.timing(backdropOpacity, {
          toValue: 1,
          duration: 160,
          useNativeDriver: true
        }),
        Animated.spring(sheetTranslateY, {
          toValue: 0,
          tension: 72,
          friction: 12,
          useNativeDriver: true
        })
      ]).start();
      return;
    }

    if (!shouldRender) {
      return;
    }

    Animated.parallel([
      Animated.timing(backdropOpacity, {
        toValue: 0,
        duration: 160,
        useNativeDriver: true
      }),
      Animated.timing(sheetTranslateY, {
        toValue: SHEET_HIDDEN_TRANSLATE_Y,
        duration: 200,
        useNativeDriver: true
      })
    ]).start(() => {
      setShouldRender(false);
    });
  }, [backdropOpacity, sheetTranslateY, shouldRender, visible]);

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_event, gesture) =>
          gesture.dy > 8 && Math.abs(gesture.dy) > Math.abs(gesture.dx),
        onPanResponderMove: (_event, gesture) => {
          sheetTranslateY.setValue(Math.max(0, gesture.dy));
        },
        onPanResponderRelease: (_event, gesture) => {
          if (gesture.dy > SWIPE_DISMISS_DISTANCE_PX || gesture.vy >= SWIPE_DISMISS_VELOCITY) {
            closeWithSheetAnimation();
            return;
          }
          Animated.spring(sheetTranslateY, {
            toValue: 0,
            tension: 84,
            friction: 11,
            useNativeDriver: true
          }).start();
        },
        onPanResponderTerminate: () => {
          Animated.spring(sheetTranslateY, {
            toValue: 0,
            tension: 84,
            friction: 11,
            useNativeDriver: true
          }).start();
        }
      }),
    [closeWithSheetAnimation, sheetTranslateY]
  );

  if (!shouldRender) {
    return null;
  }

  return (
    <Modal visible={shouldRender} transparent animationType="none" onRequestClose={closeWithSheetAnimation}>
      <Animated.View style={[styles.scrimWrap, { opacity: backdropOpacity }]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="关闭商品页"
          style={styles.scrim}
          onPress={closeWithSheetAnimation}
        />
      </Animated.View>
      <Animated.View style={[styles.sheet, { transform: [{ translateY: sheetTranslateY }] }]}>
        <View style={styles.handleTouchArea} {...panResponder.panHandlers}>
          <View style={styles.handle} />
        </View>
        <View style={styles.header}>
          <View style={styles.badge}>
            <Ionicons name="cart-outline" size={16} color={colors.accent} />
            <Text style={styles.badgeText}>{ad.sponsorLabel}</Text>
          </View>
        </View>
        <Text numberOfLines={2} style={styles.title}>
          {ad.productName}
        </Text>
        <Text style={styles.price}>{ad.priceText}</Text>
        <Text style={styles.description}>{ad.productDescription}</Text>
        <View style={styles.sellingPoints}>
          {ad.sellingPoints.map((point) => (
            <View key={point} style={styles.sellingPoint}>
              <Ionicons name="sparkles" size={13} color={colors.accent} />
              <Text style={styles.sellingPointText}>{point}</Text>
            </View>
          ))}
        </View>
        <Pressable style={({ pressed }) => [styles.primaryButton, pressed ? styles.primaryButtonPressed : null]}>
          <Ionicons name="bag-handle" size={20} color="#FFFFFF" />
          <Text style={styles.primaryButtonText}>立即查看</Text>
        </Pressable>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrimWrap: {
    ...StyleSheet.absoluteFillObject
  },
  scrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.18)"
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingTop: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: 36,
    borderTopLeftRadius: radii.panel,
    borderTopRightRadius: radii.panel,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.72)",
    shadowColor: "rgba(0,0,0,0.18)",
    shadowOffset: { width: 0, height: -6 },
    shadowOpacity: 1,
    shadowRadius: 20
  },
  handleTouchArea: {
    alignSelf: "stretch",
    alignItems: "center",
    justifyContent: "center",
    height: 28,
    marginTop: -4
  },
  handle: {
    alignSelf: "center",
    width: 48,
    height: 5,
    borderRadius: 3,
    backgroundColor: "rgba(28,28,30,0.18)"
  },
  header: {
    marginTop: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-start"
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,106,26,0.14)"
  },
  badgeText: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: "900"
  },
  title: {
    marginTop: spacing.lg,
    color: "#3A3A3A",
    fontSize: 26,
    fontWeight: "900",
    lineHeight: 31
  },
  price: {
    marginTop: spacing.sm,
    color: colors.accent,
    fontSize: 20,
    fontWeight: "900"
  },
  description: {
    marginTop: spacing.md,
    color: "#5F6368",
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 21
  },
  sellingPoints: {
    marginTop: spacing.lg,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  sellingPoint: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.sm,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: "#F3F4F6",
    borderWidth: 1,
    borderColor: "#E5E7EB"
  },
  sellingPointText: {
    color: "#424242",
    fontSize: 13,
    fontWeight: "800"
  },
  primaryButton: {
    marginTop: spacing.xl,
    height: 54,
    borderRadius: radii.small,
    backgroundColor: colors.accent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm
  },
  primaryButtonPressed: {
    opacity: 0.84
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 18,
    fontWeight: "900"
  }
});

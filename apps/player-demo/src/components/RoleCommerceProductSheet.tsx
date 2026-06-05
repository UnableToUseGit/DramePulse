import { Ionicons } from "@expo/vector-icons";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import type { RoleCommerceFeedAd } from "../domain/roleCommerceAds";
import { colors, radii, spacing } from "../theme";

export function RoleCommerceProductSheet({
  visible,
  ad,
  onClose
}: {
  visible: boolean;
  ad: RoleCommerceFeedAd;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable accessibilityRole="button" accessibilityLabel="关闭商品页" style={styles.scrim} onPress={onClose} />
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <View style={styles.header}>
          <View style={styles.badge}>
            <Ionicons name="cart-outline" size={16} color={colors.accent} />
            <Text style={styles.badgeText}>{ad.sponsorLabel}</Text>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel="关闭商品页" hitSlop={12} onPress={onClose}>
            <Ionicons name="close" size={24} color="rgba(255,255,255,0.64)" />
          </Pressable>
        </View>
        <Text numberOfLines={2} style={styles.title}>
          {ad.productName}
        </Text>
        <Text style={styles.price}>{ad.priceText}</Text>
        <Text style={styles.description}>{ad.productDescription}</Text>
        <View style={styles.sellingPoints}>
          {ad.sellingPoints.map((point) => (
            <View key={point} style={styles.sellingPoint}>
              <Ionicons name="sparkles" size={13} color={colors.gold} />
              <Text style={styles.sellingPointText}>{point}</Text>
            </View>
          ))}
        </View>
        <Pressable style={({ pressed }) => [styles.primaryButton, pressed ? styles.primaryButtonPressed : null]}>
          <Ionicons name="bag-handle" size={20} color={colors.text} />
          <Text style={styles.primaryButtonText}>立即查看</Text>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "transparent"
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingTop: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: 34,
    borderTopLeftRadius: 26,
    borderTopRightRadius: 26,
    backgroundColor: "rgba(12,12,14,0.97)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)"
  },
  handle: {
    alignSelf: "center",
    width: 48,
    height: 5,
    borderRadius: 3,
    backgroundColor: "rgba(255,255,255,0.24)"
  },
  header: {
    marginTop: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
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
    color: colors.text,
    fontSize: 26,
    fontWeight: "900",
    lineHeight: 31
  },
  price: {
    marginTop: spacing.sm,
    color: colors.gold,
    fontSize: 20,
    fontWeight: "900"
  },
  description: {
    marginTop: spacing.md,
    color: "rgba(255,255,255,0.76)",
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
    backgroundColor: "rgba(255,255,255,0.1)"
  },
  sellingPointText: {
    color: colors.text,
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
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  }
});

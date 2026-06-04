import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text } from "react-native";
import { colors, radii, spacing } from "../theme";

export function RoleCommerceProductCta({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.root, pressed ? styles.pressed : null]}
      onPress={onPress}
    >
      <Ionicons name="cart-outline" size={17} color={colors.text} />
      <Text numberOfLines={1} style={styles.text}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    height: 34,
    maxWidth: 168,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.22)",
    backgroundColor: "rgba(255,106,26,0.84)",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    shadowColor: colors.accent,
    shadowOpacity: 0.26,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 5 }
  },
  pressed: {
    opacity: 0.78,
    transform: [{ scale: 0.98 }]
  },
  text: {
    flexShrink: 1,
    color: colors.text,
    fontSize: 13,
    fontWeight: "900"
  }
});

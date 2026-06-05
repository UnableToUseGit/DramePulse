import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text } from "react-native";
import { colors, radii, spacing } from "../theme";

export function SeriesEpisodeBar({
  episodeCount,
  onPress
}: {
  episodeCount: number;
  onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="打开选集" style={styles.root} onPress={onPress}>
      <Text numberOfLines={1} style={styles.text}>
        选集 · 全{episodeCount}集 · 免费观看
      </Text>
      <Ionicons name="chevron-up" size={22} color={colors.text} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: 72,
    bottom: 24,
    height: 56,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.small,
    backgroundColor: "rgba(18,18,18,0.94)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  text: {
    flex: 1,
    color: colors.text,
    fontSize: 20,
    fontWeight: "900"
  }
});

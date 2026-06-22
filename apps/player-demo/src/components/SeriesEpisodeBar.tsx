import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text } from "react-native";
import { colors, playerOverlay } from "../theme";

export const SERIES_EPISODE_BAR_STYLE_SPEC = {
  left: 20,
  right: 20,
  bottom: 14,
  height: 44,
  backgroundColor: "rgba(36, 36, 40, 0.94)"
};

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
      <Ionicons name="chevron-up" size={20} color={colors.text} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: SERIES_EPISODE_BAR_STYLE_SPEC.left,
    right: SERIES_EPISODE_BAR_STYLE_SPEC.right,
    bottom: SERIES_EPISODE_BAR_STYLE_SPEC.bottom,
    height: SERIES_EPISODE_BAR_STYLE_SPEC.height,
    paddingHorizontal: 20,
    borderRadius: 12,
    backgroundColor: SERIES_EPISODE_BAR_STYLE_SPEC.backgroundColor,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  text: {
    flex: 1,
    color: colors.text,
    fontSize: 17,
    fontWeight: "900",
    letterSpacing: 0,
    ...playerOverlay.textShadow
  }
});

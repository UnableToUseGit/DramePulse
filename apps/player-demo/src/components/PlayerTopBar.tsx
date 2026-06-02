import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";
import { PlaybackRate, SpeedSelector } from "./SpeedSelector";

export function PlayerTopBar({
  playbackRate,
  isSpeedMenuOpen,
  onToggleSpeedMenu,
  onSelectPlaybackRate,
  mode = "home",
  episodeLabel,
  onBack
}: {
  playbackRate: PlaybackRate;
  isSpeedMenuOpen: boolean;
  onToggleSpeedMenu: () => void;
  onSelectPlaybackRate: (rate: PlaybackRate) => void;
  mode?: "home" | "series";
  episodeLabel?: string;
  onBack?: () => void;
}) {
  return (
    <View style={styles.root}>
      {mode === "series" ? (
        <Pressable accessibilityRole="button" style={styles.backButton} hitSlop={10} onPress={onBack}>
          <Ionicons name="chevron-back" size={30} color="#fff" />
          <Text numberOfLines={1} style={styles.backText}>
            {episodeLabel ?? "返回"}
          </Text>
        </Pressable>
      ) : (
        <Ionicons name="menu" size={30} color="#fff" />
      )}
      <View style={styles.actions}>
        <SpeedSelector
          selectedRate={playbackRate}
          isOpen={isSpeedMenuOpen}
          onToggle={onToggleSpeedMenu}
          onSelect={onSelectPlaybackRate}
        />
        {mode === "home" ? <Ionicons name="search" size={27} color="#fff" /> : <Ionicons name="ellipsis-vertical" size={25} color="#fff" />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 48,
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md
  },
  backButton: {
    maxWidth: "52%",
    minHeight: 36,
    flexDirection: "row",
    alignItems: "center"
  },
  backText: {
    flexShrink: 1,
    color: colors.text,
    fontSize: 24,
    fontWeight: "900"
  }
});

import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, playerOverlay, spacing } from "../theme";
import { PlaybackRate, SpeedSelector } from "./SpeedSelector";

export function formatEpisodeDisplayLabel(episodeLabel: string | undefined) {
  if (!episodeLabel) {
    return "返回";
  }
  const episodeMatch = episodeLabel.match(/^ep0*(\d+)$/i);
  if (!episodeMatch) {
    return episodeLabel;
  }
  return `第${Number(episodeMatch[1])}集`;
}

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
          <Ionicons name="chevron-back" size={31} color="#fff" />
          <Text numberOfLines={1} style={styles.backText}>
            {formatEpisodeDisplayLabel(episodeLabel)}
          </Text>
        </Pressable>
      ) : (
        <View style={styles.menuButton}>
          <Ionicons name="menu" size={28} color="#fff" />
        </View>
      )}
      <View style={styles.actions}>
        <SpeedSelector
          selectedRate={playbackRate}
          isOpen={isSpeedMenuOpen}
          onToggle={onToggleSpeedMenu}
          onSelect={onSelectPlaybackRate}
        />
        <View style={mode === "home" ? styles.iconButtonGhost : styles.iconButtonGhostNarrow}>
          {mode === "home" ? (
            <Ionicons name="search" size={27} color="#fff" />
          ) : (
            <Ionicons name="ellipsis-vertical" size={24} color="#fff" />
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 50,
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  backButton: {
    maxWidth: "56%",
    minHeight: playerOverlay.topButtonHeight,
    flexDirection: "row",
    alignItems: "center",
    paddingRight: spacing.sm
  },
  backText: {
    flexShrink: 1,
    color: colors.text,
    fontSize: 22,
    fontWeight: "900",
    letterSpacing: -0.2
  },
  menuButton: {
    width: playerOverlay.iconButtonSize,
    height: playerOverlay.iconButtonSize,
    alignItems: "center",
    justifyContent: "center"
  },
  iconButtonGhost: {
    width: playerOverlay.iconButtonSize,
    height: playerOverlay.iconButtonSize,
    alignItems: "center",
    justifyContent: "center"
  },
  iconButtonGhostNarrow: {
    width: 34,
    height: playerOverlay.iconButtonSize,
    alignItems: "center",
    justifyContent: "center"
  }
});

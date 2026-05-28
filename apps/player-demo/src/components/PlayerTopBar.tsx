import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, View } from "react-native";
import { spacing } from "../theme";
import { PlaybackRate, SpeedSelector } from "./SpeedSelector";

export function PlayerTopBar({
  playbackRate,
  isSpeedMenuOpen,
  onToggleSpeedMenu,
  onSelectPlaybackRate
}: {
  playbackRate: PlaybackRate;
  isSpeedMenuOpen: boolean;
  onToggleSpeedMenu: () => void;
  onSelectPlaybackRate: (rate: PlaybackRate) => void;
}) {
  return (
    <View style={styles.root}>
      <Ionicons name="menu" size={30} color="#fff" />
      <View style={styles.actions}>
        <SpeedSelector
          selectedRate={playbackRate}
          isOpen={isSpeedMenuOpen}
          onToggle={onToggleSpeedMenu}
          onSelect={onSelectPlaybackRate}
        />
        <Ionicons name="search" size={27} color="#fff" />
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
  }
});

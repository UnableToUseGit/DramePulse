import { StyleSheet, View } from "react-native";
import type { ReactNode } from "react";
import { PlayerActionRail } from "./PlayerActionRail";
import { PlayerBottomTabs } from "./PlayerBottomTabs";
import { PlayerMeta } from "./PlayerMeta";
import { PlaybackRate } from "./SpeedSelector";
import { PlayerTopBar } from "./PlayerTopBar";

export function PlayerChrome({
  liked,
  onToggleLike,
  onOpenStoryQa,
  onOpenTheater,
  onBack,
  playbackRate,
  isSpeedMenuOpen,
  onToggleSpeedMenu,
  onSelectPlaybackRate,
  title,
  plotSummary,
  episodeLabel,
  showActionRail = true,
  showMeta = true,
  mode = "home",
  children
}: {
  liked: boolean;
  onToggleLike: () => void;
  onOpenStoryQa: () => void;
  onOpenTheater?: () => void;
  onBack?: () => void;
  playbackRate: PlaybackRate;
  isSpeedMenuOpen: boolean;
  onToggleSpeedMenu: () => void;
  onSelectPlaybackRate: (rate: PlaybackRate) => void;
  title: string;
  plotSummary: string;
  episodeLabel?: string;
  showActionRail?: boolean;
  showMeta?: boolean;
  mode?: "home" | "series";
  children?: ReactNode;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <PlayerTopBar
        playbackRate={playbackRate}
        isSpeedMenuOpen={isSpeedMenuOpen}
        onToggleSpeedMenu={onToggleSpeedMenu}
        onSelectPlaybackRate={onSelectPlaybackRate}
        mode={mode}
        episodeLabel={episodeLabel}
        onBack={onBack}
      />
      {showActionRail ? <PlayerActionRail liked={liked} onToggleLike={onToggleLike} onOpenStoryQa={onOpenStoryQa} /> : null}
      {showMeta ? <PlayerMeta title={title} plotSummary={plotSummary} episodeLabel={episodeLabel} /> : null}
      {children}
      {mode === "home" ? <PlayerBottomTabs activeTab="首页" onPressTheater={onOpenTheater} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  }
});

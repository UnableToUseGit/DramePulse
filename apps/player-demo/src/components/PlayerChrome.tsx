import { StyleSheet, View } from "react-native";
import { PlayerActionRail } from "./PlayerActionRail";
import { PlayerBottomTabs } from "./PlayerBottomTabs";
import { PlayerMeta } from "./PlayerMeta";
import { PlaybackRate } from "./SpeedSelector";
import { PlayerTopBar } from "./PlayerTopBar";

export function PlayerChrome({
  liked,
  onToggleLike,
  onOpenStoryQa,
  playbackRate,
  isSpeedMenuOpen,
  onToggleSpeedMenu,
  onSelectPlaybackRate,
  title,
  plotSummary,
  episodeLabel,
  showActionRail = true,
  showMeta = true,
  showBottomTabs = true
}: {
  liked: boolean;
  onToggleLike: () => void;
  onOpenStoryQa: () => void;
  playbackRate: PlaybackRate;
  isSpeedMenuOpen: boolean;
  onToggleSpeedMenu: () => void;
  onSelectPlaybackRate: (rate: PlaybackRate) => void;
  title: string;
  plotSummary: string;
  episodeLabel?: string;
  showActionRail?: boolean;
  showMeta?: boolean;
  showBottomTabs?: boolean;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <PlayerTopBar
        playbackRate={playbackRate}
        isSpeedMenuOpen={isSpeedMenuOpen}
        onToggleSpeedMenu={onToggleSpeedMenu}
        onSelectPlaybackRate={onSelectPlaybackRate}
      />
      {showActionRail ? <PlayerActionRail liked={liked} onToggleLike={onToggleLike} onOpenStoryQa={onOpenStoryQa} /> : null}
      {showMeta ? <PlayerMeta title={title} plotSummary={plotSummary} episodeLabel={episodeLabel} /> : null}
      {showBottomTabs ? <PlayerBottomTabs /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  }
});

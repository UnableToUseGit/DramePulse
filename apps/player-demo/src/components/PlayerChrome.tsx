import { StyleSheet, View } from "react-native";
import type { ResonanceTapState } from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
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
  currentTime,
  isActive,
  showInnerVoice,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku,
  resonanceCue,
  resonanceTapState,
  onParticipateResonance
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
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
  resonanceCue?: ActionRailResonanceCue;
  resonanceTapState: ResonanceTapState;
  onParticipateResonance: (cue: ActionRailResonanceCue, nextState: ResonanceTapState) => void;
}) {
  return (
    <View pointerEvents="box-none" style={styles.root}>
      <PlayerTopBar
        playbackRate={playbackRate}
        isSpeedMenuOpen={isSpeedMenuOpen}
        onToggleSpeedMenu={onToggleSpeedMenu}
        onSelectPlaybackRate={onSelectPlaybackRate}
      />
      <PlayerActionRail
        liked={liked}
        onToggleLike={onToggleLike}
        onOpenStoryQa={onOpenStoryQa}
        resonanceCue={resonanceCue}
        resonanceTapState={resonanceTapState}
        onParticipateResonance={onParticipateResonance}
      />
      <PlayerMeta
        title={title}
        plotSummary={plotSummary}
        episodeLabel={episodeLabel}
        currentTime={currentTime}
        isActive={isActive}
        showInnerVoice={showInnerVoice}
        onInnerVoiceGestureActiveChange={onInnerVoiceGestureActiveChange}
        onSendInnerVoiceDanmaku={onSendInnerVoiceDanmaku}
      />
      <PlayerBottomTabs />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  }
});

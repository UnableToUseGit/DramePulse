import { StyleSheet, View } from "react-native";
import type { ReactNode } from "react";
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
  onOpenTheater,
  onBack,
  playbackRate,
  isSpeedMenuOpen,
  onToggleSpeedMenu,
  onSelectPlaybackRate,
  title,
  plotSummary,
  episodeLabel,
  metaTags,
  preTitleAccessory,
  showActionRail = true,
  showMeta = true,
  showDanmakuEntry = true,
  mode = "home",
  currentTime,
  isActive,
  showInnerVoice,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku,
  resonanceCue,
  resonanceTapState,
  onParticipateResonance,
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
  metaTags?: string[];
  preTitleAccessory?: ReactNode;
  showActionRail?: boolean;
  showMeta?: boolean;
  showDanmakuEntry?: boolean;
  mode?: "home" | "series";
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
  resonanceCue?: ActionRailResonanceCue;
  resonanceTapState: ResonanceTapState;
  onParticipateResonance: (cue: ActionRailResonanceCue, nextState: ResonanceTapState) => void;
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
      {showActionRail ? (
        <PlayerActionRail
          liked={liked}
          onToggleLike={onToggleLike}
          onOpenStoryQa={onOpenStoryQa}
          resonanceCue={resonanceCue}
          resonanceTapState={resonanceTapState}
          onParticipateResonance={onParticipateResonance}
        />
      ) : null}
      {showMeta ? (
        <PlayerMeta
          title={title}
          plotSummary={plotSummary}
          episodeLabel={episodeLabel}
          metaTags={metaTags}
          preTitleAccessory={preTitleAccessory}
          currentTime={currentTime}
          isActive={isActive}
          showInnerVoice={showInnerVoice}
          showDanmakuEntry={showDanmakuEntry}
          reserveActionRail={showActionRail}
          onInnerVoiceGestureActiveChange={onInnerVoiceGestureActiveChange}
          onSendInnerVoiceDanmaku={onSendInnerVoiceDanmaku}
        />
      ) : null}
      {showMeta ? children : null}
      {mode === "home" ? <PlayerBottomTabs activeTab="首页" onPressTheater={onOpenTheater} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  }
});

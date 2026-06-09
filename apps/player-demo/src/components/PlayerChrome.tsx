import { StyleSheet, View } from "react-native";
import type { ReactNode } from "react";
import type { ResonanceTapState } from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { PlayerActionRail } from "./PlayerActionRail";
import { PlayerMeta } from "./PlayerMeta";
import { PlaybackRate } from "./SpeedSelector";
import { PlayerTopBar } from "./PlayerTopBar";

export function PlayerChrome({
  liked,
  onToggleLike,
  onOpenWatchAssistant,
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
  metaBottomOffset,
  actionRailBottomOffset,
  preTitleAccessory,
  showActionRail = true,
  showMeta = true,
  showDanmakuEntry = true,
  mode = "home",
  currentTime,
  isActive,
  showInnerVoice,
  innerVoiceCue,
  showInnerVoiceExample,
  onInnerVoiceGestureActiveChange,
  onSendInnerVoiceDanmaku,
  onInnerVoiceExitComplete,
  resonanceCue,
  resonanceTapState,
  onParticipateResonance,
  children
}: {
  liked: boolean;
  onToggleLike: () => void;
  onOpenWatchAssistant: () => void;
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
  metaBottomOffset?: number;
  actionRailBottomOffset?: number;
  preTitleAccessory?: ReactNode;
  showActionRail?: boolean;
  showMeta?: boolean;
  showDanmakuEntry?: boolean;
  mode?: "home" | "series";
  currentTime: number;
  isActive: boolean;
  showInnerVoice: boolean;
  innerVoiceCue?: InnerVoiceDanmakuCue;
  showInnerVoiceExample?: boolean;
  onInnerVoiceGestureActiveChange: (active: boolean) => void;
  onSendInnerVoiceDanmaku: (cue: InnerVoiceDanmakuCue) => void;
  onInnerVoiceExitComplete: (cue: InnerVoiceDanmakuCue) => void;
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
          bottomOffset={actionRailBottomOffset}
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
          bottomOffset={metaBottomOffset}
          preTitleAccessory={preTitleAccessory}
          currentTime={currentTime}
          isActive={isActive}
          showInnerVoice={showInnerVoice}
          innerVoiceCue={innerVoiceCue}
          showInnerVoiceExample={showInnerVoiceExample}
          showDanmakuEntry={showDanmakuEntry}
          onOpenWatchAssistant={onOpenWatchAssistant}
          showTags={mode !== "series"}
          summaryPresentation="inline"
          reserveActionRail={showActionRail}
          onInnerVoiceGestureActiveChange={onInnerVoiceGestureActiveChange}
          onSendInnerVoiceDanmaku={onSendInnerVoiceDanmaku}
          onInnerVoiceExitComplete={onInnerVoiceExitComplete}
        />
      ) : null}
      {showMeta ? children : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject
  }
});

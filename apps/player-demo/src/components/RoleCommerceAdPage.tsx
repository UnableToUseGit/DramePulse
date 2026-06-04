import { useCallback, useEffect, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";
import { createInitialResonanceTapState } from "../action-rail-resonance/tapState";
import type { ResonanceTapState } from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import type { RoleCommerceFeedAd } from "../domain/roleCommerceAds";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerControls } from "./PlayerControls";
import { SeekRequest, VideoStage } from "./VideoStage";

declare const require: (path: string) => number;

const AD_VIDEO_SOURCE = require("../../assets/video/ads.mp4");

export function RoleCommerceAdPage({
  ad,
  height,
  isActive,
  hasNextItem,
  nextItemLabel,
  onPlayNextItem
}: {
  ad: RoleCommerceFeedAd;
  height: number;
  isActive: boolean;
  hasNextItem: boolean;
  nextItemLabel?: string;
  onPlayNextItem: () => void;
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(1);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const didCompleteRef = useRef(false);

  useEffect(() => {
    if (isActive) {
      didCompleteRef.current = false;
    }
  }, [isActive]);

  const handleTimeChange = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleDurationChange = useCallback((nextDuration: number) => {
    setDuration(nextDuration);
  }, []);

  const handlePlayToEnd = useCallback(() => {
    if (!hasNextItem || didCompleteRef.current) {
      return;
    }
    didCompleteRef.current = true;
    onPlayNextItem();
  }, [hasNextItem, onPlayNextItem]);

  const handleSeekCommit = useCallback((time: number) => {
    didCompleteRef.current = false;
    setCurrentTime(time);
    setSeekRequest({ id: Date.now(), time });
  }, []);

  const handleSeekHandled = useCallback(() => {
    setSeekRequest(undefined);
  }, []);

  const noopSendInnerVoice = useCallback((_cue: InnerVoiceDanmakuCue) => {}, []);
  const noopParticipateResonance = useCallback(
    (_cue: ActionRailResonanceCue, _nextState: ResonanceTapState) => {},
    []
  );

  return (
    <View style={[styles.root, { height }]}>
      <VideoStage
        isStarted
        isPlaying={isActive}
        seekRequest={seekRequest}
        onStart={() => {}}
        onTimeChange={handleTimeChange}
        onDurationChange={handleDurationChange}
        onPlayToEnd={handlePlayToEnd}
        onSeekHandled={handleSeekHandled}
        playbackRate={1}
        showStartEntry={false}
        streamUrl={AD_VIDEO_SOURCE}
      />
      <PlayerChrome
        liked={false}
        onToggleLike={() => {}}
        onOpenStoryQa={() => {}}
        playbackRate={1}
        isSpeedMenuOpen={false}
        onToggleSpeedMenu={() => {}}
        onSelectPlaybackRate={() => {}}
        title={ad.productName}
        plotSummary={ad.productDescription}
        episodeLabel="广告"
        metaTags={["广告", "商品同款", ad.characterName]}
        showActionRail={false}
        showDanmakuEntry={false}
        mode="series"
        currentTime={currentTime}
        isActive={isActive}
        showInnerVoice={false}
        onInnerVoiceGestureActiveChange={() => {}}
        onSendInnerVoiceDanmaku={noopSendInnerVoice}
        resonanceTapState={createInitialResonanceTapState()}
        onParticipateResonance={noopParticipateResonance}
      />
      <PlayerControls
        currentTime={currentTime}
        duration={duration}
        hasNextEpisode={hasNextItem}
        nextEpisodeLabel={nextItemLabel}
        onSeekCommit={handleSeekCommit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    backgroundColor: "#050505",
    overflow: "hidden"
  }
});

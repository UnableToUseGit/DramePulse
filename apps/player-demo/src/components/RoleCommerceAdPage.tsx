import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { createInitialResonanceTapState } from "../action-rail-resonance/tapState";
import type { ResonanceTapState } from "../action-rail-resonance/tapState";
import type { ActionRailResonanceCue } from "../action-rail-resonance/types";
import {
  getRoleCommerceAdCompletionAction,
  getRoleCommerceAdPlaybackState,
  getRoleCommerceAdProductSheetOpenAction,
  type RoleCommerceAdPlaybackIntent
} from "../domain/roleCommerceAdPlayback";
import type { RoleCommerceFeedAd } from "../domain/roleCommerceAds";
import type { InnerVoiceDanmakuCue } from "../inner-voice-danmaku/types";
import { PlaybackHint } from "./PlaybackHint";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerControls } from "./PlayerControls";
import { RoleCommerceProductCta } from "./RoleCommerceProductCta";
import { RoleCommerceProductSheet } from "./RoleCommerceProductSheet";
import { SeekRequest, VideoStage } from "./VideoStage";

declare const require: (path: string) => number;

const AD_VIDEO_SOURCE = require("../../assets/video/ads.mp4");

export function RoleCommerceAdPage({
  ad,
  height,
  videoHeight,
  controlsBottomOffset,
  metaBottomOffset,
  isActive,
  hasNextItem,
  nextItemLabel
}: {
  ad: RoleCommerceFeedAd;
  height: number;
  videoHeight: number;
  controlsBottomOffset: number;
  metaBottomOffset: number;
  isActive: boolean;
  hasNextItem: boolean;
  nextItemLabel?: string;
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(1);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [userPlaybackIntent, setUserPlaybackIntent] = useState<RoleCommerceAdPlaybackIntent>("playing");
  const [isProductSheetVisible, setIsProductSheetVisible] = useState(false);
  const didCompleteRef = useRef(false);
  const playbackState = getRoleCommerceAdPlaybackState({ isActive, userPlaybackIntent });
  const completionAction = getRoleCommerceAdCompletionAction();

  useEffect(() => {
    if (isActive) {
      didCompleteRef.current = false;
      setUserPlaybackIntent("playing");
    } else {
      setIsProductSheetVisible(false);
    }
  }, [isActive]);

  const handleTimeChange = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleDurationChange = useCallback((nextDuration: number) => {
    setDuration(nextDuration);
  }, []);

  const handlePlayToEnd = useCallback(() => {
    if (didCompleteRef.current) {
      return;
    }
    didCompleteRef.current = true;
    setCurrentTime(duration);
    setUserPlaybackIntent(completionAction.nextPlaybackIntent);
  }, [completionAction.nextPlaybackIntent, duration]);

  const handleTogglePlay = useCallback(() => {
    if (!isActive) {
      return;
    }
    if (didCompleteRef.current) {
      didCompleteRef.current = false;
      setCurrentTime(0);
      setSeekRequest({ id: Date.now(), time: 0 });
      setUserPlaybackIntent("playing");
      return;
    }
    setUserPlaybackIntent((intent) => (intent === "playing" ? "paused" : "playing"));
  }, [isActive]);

  const handleSeekCommit = useCallback((time: number) => {
    didCompleteRef.current = false;
    setCurrentTime(time);
    setUserPlaybackIntent("playing");
    setSeekRequest({ id: Date.now(), time });
  }, []);

  const handleSeekHandled = useCallback(() => {
    setSeekRequest(undefined);
  }, []);

  const handleOpenProductSheet = useCallback(() => {
    if (!isActive) {
      return;
    }
    const action = getRoleCommerceAdProductSheetOpenAction({ currentPlaybackIntent: userPlaybackIntent });
    setUserPlaybackIntent(action.nextPlaybackIntent);
    setIsProductSheetVisible(action.shouldShowProductSheet);
  }, [isActive, userPlaybackIntent]);

  const handleCloseProductSheet = useCallback(() => {
    setIsProductSheetVisible(false);
  }, []);

  const noopSendInnerVoice = useCallback((_cue: InnerVoiceDanmakuCue) => {}, []);
  const noopParticipateResonance = useCallback(
    (_cue: ActionRailResonanceCue, _nextState: ResonanceTapState) => {},
    []
  );

  return (
    <View style={[styles.root, { height }]}>
      <View style={[styles.videoViewport, { height: videoHeight }]}>
        <VideoStage
          isStarted={playbackState.isStarted}
          isPlaying={playbackState.shouldPlay}
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
        {isActive ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
        <PlaybackHint visible={playbackState.shouldShowPauseHint} />
      </View>
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
        metaBottomOffset={metaBottomOffset}
        preTitleAccessory={<RoleCommerceProductCta label={ad.ctaText} onPress={handleOpenProductSheet} />}
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
        hasNextEpisode={completionAction.shouldShowNextItemHint && hasNextItem}
        nextEpisodeLabel={nextItemLabel}
        bottomOffset={controlsBottomOffset}
        onSeekCommit={handleSeekCommit}
      />
      <RoleCommerceProductSheet visible={isProductSheetVisible} ad={ad} onClose={handleCloseProductSheet} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    backgroundColor: "#050505",
    overflow: "hidden"
  },
  videoViewport: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    overflow: "hidden",
    backgroundColor: "#050505"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject
  }
});

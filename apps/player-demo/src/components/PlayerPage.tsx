import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ENABLE_INTERACTION_LAB } from "../config";
import { getResumePlaybackTime, getVideoPlaybackState, UserPlaybackIntent } from "../domain/playerFeed";
import { PlayerVideo } from "../domain/playerApi";
import { useDanmakuFeed } from "../hooks/useDanmakuFeed";
import { useInteractionExampleState } from "../hooks/useInteractionExampleState";
import { usePlaybackSpeedControls } from "../hooks/usePlaybackSpeedControls";
import { DEFAULT_INTERACTION_EXAMPLE } from "../interaction-examples/examples";
import { InteractionExampleRenderer } from "../interaction-examples/InteractionExampleRenderer";
import { InteractionLabControls } from "../interaction-examples/InteractionLabControls";
import { shouldResetExample } from "../interaction-examples/trigger";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { DanmakuLayer } from "./DanmakuLayer";
import { FastForwardPressLayer } from "./FastForwardPressLayer";
import { FloatingStoryQaButton } from "./FloatingStoryQaButton";
import { PlaybackHint } from "./PlaybackHint";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerControls } from "./PlayerControls";
import { SeekRequest, VideoStage } from "./VideoStage";

const UI_TIME_UPDATE_INTERVAL_SEC = 1;

export function PlayerPage({
  video,
  isActive,
  shouldMountVideo,
  height,
  initialPlaybackTime,
  hasNextEpisode,
  nextEpisodeLabel,
  selectedPresentationType,
  onChangePresentationType,
  onPlaybackPositionChange,
  onPlayNextEpisode,
  onOpenTheater,
  onOpenSeriesDetails,
  onOpenStoryQaPage
}: {
  video: PlayerVideo;
  isActive: boolean;
  shouldMountVideo: boolean;
  height: number;
  initialPlaybackTime?: number;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  selectedPresentationType: InteractionPresentationType;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onPlaybackPositionChange: (videoId: string, time: number) => void;
  onPlayNextEpisode: () => void;
  onOpenTheater: () => void;
  onOpenSeriesDetails: (video: PlayerVideo) => void;
  onOpenStoryQaPage: (video: PlayerVideo, currentTime: number) => void;
}) {
  const { danmaku, danmakuState } = useDanmakuFeed(video.danmakuUrl);
  const [currentTime, setCurrentTime] = useState(0);
  const [userPlaybackIntent, setUserPlaybackIntent] = useState<UserPlaybackIntent>("playing");
  const [resolvedDuration, setResolvedDuration] = useState(video.duration);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [liked, setLiked] = useState(false);
  const previousTimeRef = useRef(0);
  const lastPublishedTimeRef = useRef(0);
  const didCompleteRef = useRef(false);
  const wasActiveRef = useRef(false);
  const previousVideoIdRef = useRef(video.videoId);
  const lastReportedPositionRef = useRef(0);
  const playbackState = getVideoPlaybackState({ isActive, userPlaybackIntent });
  const {
    dismiss: dismissInteractionExample,
    reset: resetInteractionExample,
    visible: isInteractionExampleVisible
  } = useInteractionExampleState({
    currentTime,
    example: DEFAULT_INTERACTION_EXAMPLE,
    isActive,
    isStarted: playbackState.isStarted,
    presentationType: selectedPresentationType,
    resetKey: video.videoId
  });

  const handleTogglePlay = useCallback(() => {
    if (!isActive) {
      return;
    }
    setUserPlaybackIntent((intent) => (intent === "playing" ? "paused" : "playing"));
  }, [isActive]);

  const handleResume = useCallback(() => {
    if (!isActive) {
      return;
    }
    setUserPlaybackIntent("playing");
  }, [isActive]);

  const speedControls = usePlaybackSpeedControls({
    isActive,
    isStarted: playbackState.isStarted,
    onResume: handleResume,
    onStart: handleResume,
    onTap: handleTogglePlay,
    resetKey: video.videoId
  });

  useEffect(() => {
    if (!isActive) {
      wasActiveRef.current = false;
      return;
    }

    const becameActive = !wasActiveRef.current;
    const videoChanged = previousVideoIdRef.current !== video.videoId;
    if (becameActive || videoChanged) {
      const resumeTime = getResumePlaybackTime({
        savedTime: initialPlaybackTime,
        duration: video.duration
      });
      setCurrentTime(resumeTime);
      setResolvedDuration(video.duration);
      setUserPlaybackIntent("playing");
      setSeekRequest(resumeTime > 0 ? { id: Date.now(), time: resumeTime } : undefined);
      setSeekVersion((version) => version + 1);
      resetInteractionExample();
      previousTimeRef.current = resumeTime;
      lastPublishedTimeRef.current = resumeTime;
      lastReportedPositionRef.current = resumeTime;
      didCompleteRef.current = false;
      previousVideoIdRef.current = video.videoId;
    }
    wasActiveRef.current = true;
  }, [initialPlaybackTime, isActive, resetInteractionExample, video.duration, video.videoId]);

  useEffect(() => {
    setResolvedDuration(video.duration);
  }, [video.duration, video.videoId]);

  const handleTimeChange = useCallback(
    (time: number) => {
      if (isActive) {
        if (
          shouldResetExample({
            previousTime: previousTimeRef.current,
            currentTime: time,
            triggerTimeSec: DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec
          })
        ) {
          resetInteractionExample();
        }
        previousTimeRef.current = time;
        const previousPublishedTime = lastPublishedTimeRef.current;
        const isCloseToEnd = resolvedDuration > 0 && resolvedDuration - time <= 4;
        const didCountdownSecondChange =
          isCloseToEnd && Math.ceil(resolvedDuration - time) !== Math.ceil(resolvedDuration - previousPublishedTime);
        if (Math.abs(time - previousPublishedTime) >= UI_TIME_UPDATE_INTERVAL_SEC || didCountdownSecondChange) {
          lastPublishedTimeRef.current = time;
          setCurrentTime(time);
        }
        if (Math.abs(time - lastReportedPositionRef.current) >= UI_TIME_UPDATE_INTERVAL_SEC) {
          lastReportedPositionRef.current = time;
          onPlaybackPositionChange(video.videoId, time);
        }
        if (
          hasNextEpisode &&
          playbackState.shouldPlay &&
          resolvedDuration > 0 &&
          time >= Math.max(0, resolvedDuration - 0.2) &&
          !didCompleteRef.current
        ) {
          didCompleteRef.current = true;
          onPlayNextEpisode();
        }
      }
    },
    [
      hasNextEpisode,
      isActive,
      onPlayNextEpisode,
      onPlaybackPositionChange,
      playbackState.shouldPlay,
      resetInteractionExample,
      resolvedDuration,
      video.videoId
    ]
  );

  const handleDurationChange = useCallback((duration: number) => {
    setResolvedDuration(duration);
  }, []);

  const handlePlayToEnd = useCallback(() => {
    if (!isActive || !hasNextEpisode || didCompleteRef.current) {
      return;
    }
    didCompleteRef.current = true;
    onPlayNextEpisode();
  }, [hasNextEpisode, isActive, onPlayNextEpisode]);

  const handleSeekHandled = useCallback(() => {
    setSeekRequest(undefined);
  }, []);

  const handleSeekCommit = useCallback(
    (time: number) => {
      if (!isActive) {
        return;
      }
      setCurrentTime(time);
      lastPublishedTimeRef.current = time;
      previousTimeRef.current = time;
      lastReportedPositionRef.current = time;
      onPlaybackPositionChange(video.videoId, time);
      didCompleteRef.current = false;
      if (time < DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec) {
        resetInteractionExample();
      }
      setUserPlaybackIntent("playing");
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time });
    },
    [isActive, onPlaybackPositionChange, resetInteractionExample, video.videoId]
  );

  return (
    <View style={[styles.root, { height }]}>
      {shouldMountVideo ? (
        <VideoStage
          key={`${video.videoId}:${video.streamUrl}`}
          isStarted={playbackState.isStarted}
          isPlaying={playbackState.shouldPlay}
          seekRequest={seekRequest}
          onStart={handleResume}
          onTimeChange={handleTimeChange}
          onDurationChange={handleDurationChange}
          onPlayToEnd={handlePlayToEnd}
          onSeekHandled={handleSeekHandled}
          playbackRate={speedControls.effectivePlaybackRate}
          showStartEntry={false}
          streamUrl={video.streamUrl}
        />
      ) : (
        <View style={styles.inactiveVideoPlaceholder} />
      )}
      {isActive && playbackState.isStarted && danmakuState === "ready" ? (
        <DanmakuLayer currentTime={currentTime} danmaku={danmaku} isPlaying={playbackState.shouldPlay} seekVersion={seekVersion} />
      ) : null}
      {isActive && playbackState.isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
      {isActive && playbackState.isStarted ? (
        <FastForwardPressLayer
          isHoldingFastForward={speedControls.isHoldingFastForward}
          onPress={speedControls.handleRightPress}
          onLongPress={speedControls.handleRightLongPress}
          onPressOut={speedControls.handleRightPressOut}
        />
      ) : null}
      {isActive && danmakuState === "error" ? <Text style={styles.danmakuError}>弹幕暂不可用</Text> : null}
      <PlaybackHint visible={playbackState.shouldShowPauseHint} />
      <InteractionExampleRenderer
        example={DEFAULT_INTERACTION_EXAMPLE}
        presentationType={selectedPresentationType}
        visible={isInteractionExampleVisible}
        onDismiss={dismissInteractionExample}
      />
      <PlayerChrome
        liked={liked}
        onToggleLike={() => setLiked((current) => !current)}
        onOpenSeriesDetails={() => onOpenSeriesDetails(video)}
        onOpenTheater={onOpenTheater}
        playbackRate={speedControls.playbackRate}
        isSpeedMenuOpen={speedControls.isSpeedMenuOpen}
        onToggleSpeedMenu={speedControls.toggleSpeedMenu}
        onSelectPlaybackRate={speedControls.selectPlaybackRate}
        title={video.title}
        plotSummary={video.plotSummary}
        episodeLabel={video.episodeLabel}
      />
      {isActive ? <FloatingStoryQaButton onPress={() => onOpenStoryQaPage(video, currentTime)} /> : null}
      {ENABLE_INTERACTION_LAB && isActive ? (
        <InteractionLabControls selectedType={selectedPresentationType} onChange={onChangePresentationType} />
      ) : null}
      <PlayerControls
        currentTime={currentTime}
        duration={resolvedDuration}
        hasNextEpisode={hasNextEpisode}
        nextEpisodeLabel={nextEpisodeLabel}
        onSeekCommit={handleSeekCommit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    backgroundColor: "#050505",
    overflow: "hidden"
  },
  inactiveVideoPlaceholder: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#050505"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject
  },
  danmakuError: {
    position: "absolute",
    top: 92,
    alignSelf: "center",
    color: "rgba(255,255,255,0.68)",
    fontSize: 12,
    fontWeight: "700",
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: "rgba(0,0,0,0.36)",
    borderRadius: 6
  }
});

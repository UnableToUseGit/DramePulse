import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ENABLE_INTERACTION_LAB } from "../config";
import { getFeedPlaybackMode } from "../domain/playerFeed";
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
  hasStartedFeed,
  hasNextEpisode,
  nextEpisodeLabel,
  selectedPresentationType,
  onChangePresentationType,
  onStartFeed,
  onPlayNextEpisode
}: {
  video: PlayerVideo;
  isActive: boolean;
  shouldMountVideo: boolean;
  height: number;
  hasStartedFeed: boolean;
  hasNextEpisode: boolean;
  nextEpisodeLabel?: string;
  selectedPresentationType: InteractionPresentationType;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onStartFeed: () => void;
  onPlayNextEpisode: () => void;
}) {
  const { danmaku, danmakuState } = useDanmakuFeed(video.danmakuUrl);
  const [currentTime, setCurrentTime] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [resolvedDuration, setResolvedDuration] = useState(video.duration);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [liked, setLiked] = useState(false);
  const previousTimeRef = useRef(0);
  const lastPublishedTimeRef = useRef(0);
  const didCompleteRef = useRef(false);
  const wasActiveRef = useRef(false);
  const previousVideoIdRef = useRef(video.videoId);
  const playbackMode = useMemo(
    () => getFeedPlaybackMode({ hasStartedFeed, isActive }),
    [hasStartedFeed, isActive]
  );
  const canPlay = isActive && isStarted && isPlaying;
  const {
    dismiss: dismissInteractionExample,
    reset: resetInteractionExample,
    visible: isInteractionExampleVisible
  } = useInteractionExampleState({
    currentTime,
    example: DEFAULT_INTERACTION_EXAMPLE,
    isActive,
    isStarted,
    presentationType: selectedPresentationType,
    resetKey: video.videoId
  });

  const handleStart = useCallback(() => {
    if (!isActive) {
      return;
    }
    onStartFeed();
    setIsStarted(true);
    setIsPlaying(true);
  }, [isActive, onStartFeed]);

  const handleTogglePlay = useCallback(() => {
    if (!isActive) {
      return;
    }
    if (!isStarted) {
      handleStart();
      return;
    }
    setIsPlaying((playing) => !playing);
  }, [handleStart, isActive, isStarted]);

  const handleResume = useCallback(() => {
    if (!isActive) {
      return;
    }
    setIsPlaying(true);
  }, [isActive]);

  const speedControls = usePlaybackSpeedControls({
    isActive,
    isStarted,
    onResume: handleResume,
    onStart: handleStart,
    onTap: handleTogglePlay,
    resetKey: video.videoId
  });

  useEffect(() => {
    if (!isActive) {
      setIsPlaying(false);
      wasActiveRef.current = false;
      return;
    }

    const becameActive = !wasActiveRef.current;
    const videoChanged = previousVideoIdRef.current !== video.videoId;
    if (becameActive || videoChanged) {
      setCurrentTime(0);
      setResolvedDuration(video.duration);
      setIsStarted(playbackMode.shouldAutoStart);
      setIsPlaying(playbackMode.shouldAutoStart);
      setSeekRequest(undefined);
      setSeekVersion((version) => version + 1);
      resetInteractionExample();
      previousTimeRef.current = 0;
      lastPublishedTimeRef.current = 0;
      didCompleteRef.current = false;
      previousVideoIdRef.current = video.videoId;
    }
    wasActiveRef.current = true;
  }, [isActive, playbackMode.shouldAutoStart, resetInteractionExample, video.duration, video.videoId]);

  useEffect(() => {
    setResolvedDuration(video.duration);
  }, [video.videoId]);

  useEffect(() => {
    if (playbackMode.shouldAutoStart && !isStarted) {
      setIsStarted(true);
      setIsPlaying(true);
    }
  }, [isStarted, playbackMode.shouldAutoStart]);

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
        if (
          Math.abs(time - previousPublishedTime) >= UI_TIME_UPDATE_INTERVAL_SEC ||
          didCountdownSecondChange
        ) {
          lastPublishedTimeRef.current = time;
          setCurrentTime(time);
        }
        if (
          hasNextEpisode &&
          isStarted &&
          isPlaying &&
          resolvedDuration > 0 &&
          time >= Math.max(0, resolvedDuration - 0.2) &&
          !didCompleteRef.current
        ) {
          didCompleteRef.current = true;
          onPlayNextEpisode();
        }
      }
    },
    [hasNextEpisode, isActive, isPlaying, isStarted, onPlayNextEpisode, resetInteractionExample, resolvedDuration]
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
      didCompleteRef.current = false;
      if (time < DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec) {
        resetInteractionExample();
      }
      setIsStarted(true);
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time });
    },
    [isActive, resetInteractionExample]
  );

  return (
    <View style={[styles.root, { height }]}>
      {shouldMountVideo ? (
        <VideoStage
          key={`${video.videoId}:${video.streamUrl}`}
          isStarted={isStarted}
          isPlaying={isActive && isStarted && isPlaying}
          seekRequest={seekRequest}
          onStart={handleStart}
          onTimeChange={handleTimeChange}
          onDurationChange={handleDurationChange}
          onPlayToEnd={handlePlayToEnd}
          onSeekHandled={handleSeekHandled}
          playbackRate={speedControls.effectivePlaybackRate}
          showStartEntry={playbackMode.shouldShowStartEntry}
          streamUrl={video.streamUrl}
        />
      ) : (
        <View style={styles.inactiveVideoPlaceholder} />
      )}
      {isActive && isStarted && danmakuState === "ready" ? (
        <DanmakuLayer currentTime={currentTime} danmaku={danmaku} isPlaying={canPlay} seekVersion={seekVersion} />
      ) : null}
      {isActive && isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
      {isActive && isStarted ? (
        <FastForwardPressLayer
          isHoldingFastForward={speedControls.isHoldingFastForward}
          onPress={speedControls.handleRightPress}
          onLongPress={speedControls.handleRightLongPress}
          onPressOut={speedControls.handleRightPressOut}
        />
      ) : null}
      {isActive && danmakuState === "error" ? <Text style={styles.danmakuError}>弹幕暂不可用</Text> : null}
      <PlaybackHint isStarted={isStarted} isPlaying={canPlay} />
      <InteractionExampleRenderer
        example={DEFAULT_INTERACTION_EXAMPLE}
        presentationType={selectedPresentationType}
        visible={isInteractionExampleVisible}
        onDismiss={dismissInteractionExample}
      />
      <PlayerChrome
        liked={liked}
        onToggleLike={() => setLiked((current) => !current)}
        playbackRate={speedControls.playbackRate}
        isSpeedMenuOpen={speedControls.isSpeedMenuOpen}
        onToggleSpeedMenu={speedControls.toggleSpeedMenu}
        onSelectPlaybackRate={speedControls.selectPlaybackRate}
        title={video.title}
        plotSummary={video.plotSummary}
        episodeLabel={video.episodeLabel}
      />
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

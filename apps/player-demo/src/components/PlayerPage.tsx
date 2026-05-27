import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ENABLE_INTERACTION_LAB } from "../config";
import { getFeedPlaybackMode } from "../domain/playerFeed";
import { loadVideoDanmaku, PlayerVideo } from "../domain/playerApi";
import type { DanmakuItem } from "../domain/types";
import { DEFAULT_INTERACTION_EXAMPLE } from "../interaction-examples/examples";
import { InteractionExampleRenderer } from "../interaction-examples/InteractionExampleRenderer";
import { InteractionLabControls } from "../interaction-examples/InteractionLabControls";
import { shouldResetExample, shouldShowExample } from "../interaction-examples/trigger";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, spacing } from "../theme";
import { DanmakuLayer } from "./DanmakuLayer";
import { PlaybackHint } from "./PlaybackHint";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerControls } from "./PlayerControls";
import { RapidTapInteraction } from "./RapidTapInteraction";
import { PlaybackRate } from "./SpeedSelector";
import { SeekRequest, VideoStage } from "./VideoStage";

const RAPID_TAP_PROMPT_DURATION_SEC = 30;
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
  const [danmaku, setDanmaku] = useState<DanmakuItem[]>([]);
  const [danmakuState, setDanmakuState] = useState<"loading" | "ready" | "error">("loading");
  const [currentTime, setCurrentTime] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [resolvedDuration, setResolvedDuration] = useState(video.duration);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [exampleDismissed, setExampleDismissed] = useState(false);
  const [playbackRate, setPlaybackRate] = useState<PlaybackRate>(1);
  const [isSpeedMenuOpen, setIsSpeedMenuOpen] = useState(false);
  const [isHoldingFastForward, setIsHoldingFastForward] = useState(false);
  const previousTimeRef = useRef(0);
  const lastPublishedTimeRef = useRef(0);
  const didLongPressSpeedRef = useRef(false);
  const didCompleteRef = useRef(false);
  const wasActiveRef = useRef(false);
  const previousVideoIdRef = useRef(video.videoId);
  const playbackMode = useMemo(
    () => getFeedPlaybackMode({ hasStartedFeed, isActive }),
    [hasStartedFeed, isActive]
  );
  const canPlay = isActive && isStarted && isPlaying;
  const effectivePlaybackRate = isHoldingFastForward ? 2 : playbackRate;

  useEffect(() => {
    let cancelled = false;
    setDanmakuState("loading");
    setDanmaku([]);
    loadVideoDanmaku({ danmakuUrl: video.danmakuUrl })
      .then((items) => {
        if (!cancelled) {
          setDanmaku(items);
          setDanmakuState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDanmaku([]);
          setDanmakuState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [video.danmakuUrl]);

  useEffect(() => {
    if (!isActive) {
      setIsPlaying(false);
      setIsHoldingFastForward(false);
      setIsSpeedMenuOpen(false);
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
      setExampleDismissed(false);
      previousTimeRef.current = 0;
      lastPublishedTimeRef.current = 0;
      didCompleteRef.current = false;
      previousVideoIdRef.current = video.videoId;
    }
    wasActiveRef.current = true;
  }, [isActive, playbackMode.shouldAutoStart, video.duration, video.videoId]);

  useEffect(() => {
    setPlaybackRate(1);
    setIsSpeedMenuOpen(false);
    setIsHoldingFastForward(false);
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
          setExampleDismissed(false);
        }
        previousTimeRef.current = time;
        const previousPublishedTime = lastPublishedTimeRef.current;
        const isCloseToEnd = resolvedDuration > 0 && resolvedDuration - time <= 4;
        const didCountdownSecondChange =
          isCloseToEnd && Math.ceil(resolvedDuration - time) !== Math.ceil(resolvedDuration - previousPublishedTime);
        const didPassRapidTapTrigger =
          selectedPresentationType === "rapid_tap" &&
          previousPublishedTime < DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec &&
          time >= DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec;
        if (
          Math.abs(time - previousPublishedTime) >= UI_TIME_UPDATE_INTERVAL_SEC ||
          didCountdownSecondChange ||
          didPassRapidTapTrigger
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
    [hasNextEpisode, isActive, isPlaying, isStarted, onPlayNextEpisode, resolvedDuration, selectedPresentationType]
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

  useEffect(() => {
    setExampleDismissed(false);
  }, [selectedPresentationType, video.videoId]);

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

  const handleToggleSpeedMenu = useCallback(() => {
    setIsSpeedMenuOpen((open) => !open);
  }, []);

  const handleSelectPlaybackRate = useCallback((rate: PlaybackRate) => {
    setPlaybackRate(rate);
    setIsSpeedMenuOpen(false);
  }, []);

  const handleRightPress = useCallback(() => {
    if (didLongPressSpeedRef.current) {
      didLongPressSpeedRef.current = false;
      return;
    }
    handleTogglePlay();
  }, [handleTogglePlay]);

  const handleRightLongPress = useCallback(() => {
    if (!isActive) {
      return;
    }
    didLongPressSpeedRef.current = true;
    if (!isStarted) {
      handleStart();
    }
    setIsHoldingFastForward(true);
  }, [handleStart, isActive, isStarted]);

  const handleRightPressOut = useCallback(() => {
    setIsHoldingFastForward(false);
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
        setExampleDismissed(false);
      }
      setIsStarted(true);
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time });
    },
    [isActive]
  );

  const handleDismissExample = useCallback(() => {
    setExampleDismissed(true);
  }, []);

  const isExampleVisible = shouldShowExample({
    example: DEFAULT_INTERACTION_EXAMPLE,
    currentTime,
    isStarted: isActive && isStarted,
    dismissed: exampleDismissed,
    presentationType: selectedPresentationType
  });
  const isRapidTapWindowActive =
    selectedPresentationType === "rapid_tap" &&
    isActive &&
    isStarted &&
    currentTime >= DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec &&
    currentTime <= DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec + RAPID_TAP_PROMPT_DURATION_SEC;

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
          playbackRate={effectivePlaybackRate}
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
      {isRapidTapWindowActive ? (
        <RapidTapInteraction
          enabled
          isActive={isActive}
          isStarted={isStarted}
          currentTime={currentTime}
          triggerTimeSec={DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec}
          promptDurationSec={RAPID_TAP_PROMPT_DURATION_SEC}
          resetKey={video.videoId}
        />
      ) : null}
      {isActive && isStarted && selectedPresentationType !== "rapid_tap" ? (
        <Pressable
          style={styles.rightSpeedLayer}
          delayLongPress={260}
          onPress={handleRightPress}
          onLongPress={handleRightLongPress}
          onPressOut={handleRightPressOut}
        >
          {isHoldingFastForward ? (
            <View style={styles.fastForwardHint}>
              <Text style={styles.fastForwardText}>2x</Text>
            </View>
          ) : null}
        </Pressable>
      ) : null}
      {isActive && danmakuState === "error" ? <Text style={styles.danmakuError}>弹幕暂不可用</Text> : null}
      <PlaybackHint isStarted={isStarted} isPlaying={canPlay} />
      <InteractionExampleRenderer
        example={DEFAULT_INTERACTION_EXAMPLE}
        presentationType={selectedPresentationType}
        visible={isExampleVisible}
        onDismiss={handleDismissExample}
      />
      <PlayerChrome
        onToggleDebug={() => undefined}
        playbackRate={playbackRate}
        isSpeedMenuOpen={isSpeedMenuOpen}
        onToggleSpeedMenu={handleToggleSpeedMenu}
        onSelectPlaybackRate={handleSelectPlaybackRate}
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
  rightSpeedLayer: {
    position: "absolute",
    top: 96,
    right: 0,
    bottom: 120,
    width: "42%",
    alignItems: "center",
    justifyContent: "center"
  },
  fastForwardHint: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 999,
    backgroundColor: "rgba(0,0,0,0.56)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)"
  },
  fastForwardText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  danmakuError: {
    position: "absolute",
    top: 92,
    alignSelf: "center",
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: "rgba(0,0,0,0.36)",
    borderRadius: 6
  }
});

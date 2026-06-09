import { useEventListener } from "expo";
import { useVideoPlayer, VideoView } from "expo-video";
import type { BufferOptions, SurfaceType, VideoPlayer, VideoViewProps } from "expo-video";
import { memo, useEffect, useMemo, useRef } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import type { HomeFeedPlaybackObserver } from "../domain/homeFeedPlaybackObserver";
import { getVideoBufferHealthSample } from "../domain/videoBufferHealth";
import { getVideoPlaybackCommand, type VideoPlaybackCommand } from "../domain/videoPlayback";
import {
  createVideoReadinessState,
  reduceVideoReadinessState,
  type VideoReadinessEvent,
  type VideoReadinessState
} from "../domain/videoReadiness";
import { buildVideoStageSource } from "../domain/videoSource";
import { colors, radii, spacing } from "../theme";

export interface SeekRequest {
  id: number;
  time: number;
  reason?: string;
  blocksPlaybackUntilHandled?: boolean;
}

const DISABLED_FULLSCREEN_OPTIONS: NonNullable<VideoViewProps["fullscreenOptions"]> = { enable: false };
const VIDEO_SURFACE_TYPE: SurfaceType | undefined = Platform.OS === "android" ? "textureView" : undefined;

function ignoreReleasedPlayerError(action: () => void) {
  try {
    action();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const isReleasedPlayerError =
      message.includes("already released") ||
      message.includes("shared object") ||
      (message.includes("VideoPlayer.") && message.includes("rejected"));
    if (!isReleasedPlayerError) {
      throw error;
    }
  }
}

function applyPlaybackCommand(player: VideoPlayer, command: VideoPlaybackCommand) {
  if (!command) {
    return;
  }
  ignoreReleasedPlayerError(() => {
    if (command === "play") {
      player.play();
    } else {
      player.pause();
    }
  });
}

interface VideoStageObservation {
  observer: HomeFeedPlaybackObserver;
  videoId: string;
  pageIndex: number;
}

export const VideoStage = memo(function VideoStage({
  observation,
  isStarted,
  onStart,
  isPlaying,
  initialPlaybackTime = 0,
  seekRequest,
  onTimeChange,
  onDurationChange,
  onPlayToEnd,
  onSeekHandled,
  onPlaybackReady,
  playbackRate,
  bufferOptions,
  enableCaching = false,
  streamUrl,
  showStartEntry = true
}: {
  observation?: VideoStageObservation;
  isStarted: boolean;
  onStart: () => void;
  isPlaying: boolean;
  initialPlaybackTime?: number;
  seekRequest: SeekRequest | undefined;
  onTimeChange: (time: number) => void;
  onDurationChange: (duration: number) => void;
  onPlayToEnd: () => void;
  onSeekHandled: () => void;
  onPlaybackReady?: () => void;
  playbackRate: number;
  bufferOptions?: BufferOptions;
  enableCaching?: boolean;
  streamUrl: string | number;
  showStartEntry?: boolean;
}) {
  const onTimeChangeRef = useRef(onTimeChange);
  const lastBufferHealthReportedTimeRef = useRef<number | undefined>(undefined);
  const lastHandledSeekIdRef = useRef<number | undefined>(undefined);
  const readinessStateRef = useRef<VideoReadinessState>(createVideoReadinessState(initialPlaybackTime));
  const didReportPlaybackReadyRef = useRef(false);
  const recordObservation = (
    eventType: Parameters<HomeFeedPlaybackObserver["record"]>[0]["eventType"],
    details?: Record<string, string | number | boolean | undefined>
  ) => {
    observation?.observer.record({
      eventType,
      videoId: observation.videoId,
      pageIndex: observation.pageIndex,
      details
    });
  };
  const videoSource = useMemo(
    () => buildVideoStageSource({ enableCaching, streamUrl }),
    [enableCaching, streamUrl]
  );
  const player = useVideoPlayer(videoSource, (instance) => {
    instance.loop = false;
    instance.muted = !isStarted || !isPlaying;
    instance.timeUpdateEventInterval = 0.5;
    instance.playbackRate = playbackRate;
    if (bufferOptions) {
      instance.bufferOptions = bufferOptions;
    }
    if (initialPlaybackTime > 0) {
      instance.currentTime = initialPlaybackTime;
    }
  });
  const isPlaybackBlocked =
    seekRequest !== undefined &&
    seekRequest.id !== lastHandledSeekIdRef.current &&
    seekRequest.blocksPlaybackUntilHandled !== false;
  const reduceReadiness = (event: VideoReadinessEvent) => {
    const nextState = reduceVideoReadinessState(readinessStateRef.current, event);
    readinessStateRef.current = nextState;
    if (nextState.isReady && !didReportPlaybackReadyRef.current) {
      didReportPlaybackReadyRef.current = true;
      onPlaybackReady?.();
    }
  };

  useEffect(() => {
    readinessStateRef.current = createVideoReadinessState(initialPlaybackTime);
    didReportPlaybackReadyRef.current = false;
    recordObservation("player_create");
    if (initialPlaybackTime > 0) {
      recordObservation("resume_position_initialized", { time: initialPlaybackTime });
    }
    recordObservation("status_change", { status: player.status });
    recordObservation("playing_change", { isPlaying: player.playing });
    recordObservation("muted_change", { isMuted: player.muted });
    return () => {
      recordObservation("player_release");
    };
  }, [player]);

  useEffect(() => {
    onTimeChangeRef.current = onTimeChange;
  }, [onTimeChange]);

  useEventListener(player, "timeUpdate", ({ bufferedPosition, currentTime }) => {
    const resolvedCurrentTime = currentTime ?? 0;
    onTimeChangeRef.current(resolvedCurrentTime);
    reduceReadiness({ type: "time_update", currentTime: resolvedCurrentTime });
    const bufferHealth = getVideoBufferHealthSample({
      bufferedPosition,
      currentTime,
      isPlaying: player.playing,
      lastReportedTime: lastBufferHealthReportedTimeRef.current,
      shouldPlay: isPlaying
    });
    lastBufferHealthReportedTimeRef.current = bufferHealth.nextLastReportedTime;
    if (bufferHealth.shouldRecord) {
      recordObservation("buffer_health", bufferHealth.details);
    }
  });

  useEventListener(player, "playingChange", ({ isPlaying: playerIsPlaying }) => {
    recordObservation("playing_change", { isPlaying: playerIsPlaying });
    reduceReadiness({ type: "playing_change", isPlaying: playerIsPlaying });
    const command = getVideoPlaybackCommand({
      isStarted,
      shouldPlay: isPlaying,
      playerIsPlaying
    });
    if (command === "pause") {
      recordObservation("pause_command", { reason: "unexpected_playing_state" });
      applyPlaybackCommand(player, command);
    }
  });

  useEventListener(player, "mutedChange", ({ muted }) => {
    recordObservation("muted_change", { isMuted: muted });
  });

  useEventListener(player, "statusChange", ({ status, oldStatus, error }) => {
    recordObservation("status_change", {
      status,
      oldStatus,
      error: error?.message
    });
  });

  useEventListener(player, "playToEnd", onPlayToEnd);
  useEventListener(player, "sourceLoad", ({ duration }) => {
    recordObservation("source_load", {
      bufferedPosition: player.bufferedPosition,
      cacheEnabled: enableCaching,
      duration
    });
    if (Number.isFinite(duration) && duration > 0) {
      onDurationChange(duration);
    }
  });

  useEffect(() => {
    if (seekRequest && seekRequest.id !== lastHandledSeekIdRef.current) {
      lastHandledSeekIdRef.current = seekRequest.id;
      recordObservation("seek_requested", { time: seekRequest.time, reason: seekRequest.reason });
      ignoreReleasedPlayerError(() => {
        player.currentTime = seekRequest.time;
        recordObservation("seek_applied", { time: seekRequest.time, reason: seekRequest.reason });
      });
      onTimeChangeRef.current(seekRequest.time);
      onSeekHandled();
    }
  }, [onSeekHandled, player, seekRequest]);

  useEffect(() => {
    const shouldMute = !isStarted || !isPlaying;
    ignoreReleasedPlayerError(() => {
      player.muted = shouldMute;
    });
    recordObservation("muted_change", { isMuted: shouldMute });
    const command = getVideoPlaybackCommand({
      isStarted,
      shouldPlay: isPlaying,
      playerIsPlaying: player.playing,
      isPlaybackBlocked
    });
    if (command) {
      recordObservation(command === "play" ? "play_command" : "pause_command", {
        reason: isPlaybackBlocked ? "pending_seek" : "desired_state_reconciliation"
      });
      applyPlaybackCommand(player, command);
    }
  }, [isPlaybackBlocked, isPlaying, isStarted, player]);

  useEffect(() => {
    ignoreReleasedPlayerError(() => {
      player.playbackRate = playbackRate;
    });
  }, [playbackRate, player]);

  useEffect(() => {
    if (!bufferOptions) {
      return;
    }
    ignoreReleasedPlayerError(() => {
      player.bufferOptions = bufferOptions;
    });
  }, [bufferOptions, player]);

  return (
    <View style={styles.root}>
      <VideoView
        style={styles.video}
        player={player}
        nativeControls={false}
        contentFit="cover"
        fullscreenOptions={DISABLED_FULLSCREEN_OPTIONS}
        allowsPictureInPicture={false}
        allowsVideoFrameAnalysis={false}
        surfaceType={VIDEO_SURFACE_TYPE}
        onFirstFrameRender={() => {
          recordObservation("first_frame_render");
          reduceReadiness({ type: "first_frame_render" });
        }}
      />
      {!isStarted && showStartEntry ? (
        <View style={styles.startOverlay}>
          <Pressable style={styles.startButton} onPress={onStart}>
            <Text style={styles.startButtonText}>点击播放短剧</Text>
          </Pressable>
          <Text style={styles.startHint}>DramePulse 即时互动 Demo</Text>
        </View>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#050505"
  },
  video: {
    width: "100%",
    height: "100%"
  },
  startOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.36)"
  },
  startButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.accent
  },
  startButtonText: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  startHint: {
    marginTop: spacing.md,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700"
  }
});

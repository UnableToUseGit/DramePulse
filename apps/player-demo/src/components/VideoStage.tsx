import { useEventListener } from "expo";
import { useVideoPlayer, VideoView } from "expo-video";
import type { SurfaceType, VideoViewProps } from "expo-video";
import { memo, useEffect, useRef } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { colors, radii, spacing } from "../theme";

export interface SeekRequest {
  id: number;
  time: number;
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

export const VideoStage = memo(function VideoStage({
  isStarted,
  onStart,
  isPlaying,
  seekRequest,
  onTimeChange,
  onDurationChange,
  onPlayToEnd,
  onSeekHandled,
  playbackRate,
  streamUrl,
  showStartEntry = true
}: {
  isStarted: boolean;
  onStart: () => void;
  isPlaying: boolean;
  seekRequest: SeekRequest | undefined;
  onTimeChange: (time: number) => void;
  onDurationChange: (duration: number) => void;
  onPlayToEnd: () => void;
  onSeekHandled: () => void;
  playbackRate: number;
  streamUrl: string;
  showStartEntry?: boolean;
}) {
  const onTimeChangeRef = useRef(onTimeChange);
  const lastHandledSeekIdRef = useRef<number | undefined>(undefined);
  const playbackCommandRef = useRef<"idle" | "play" | "pause">("idle");
  const player = useVideoPlayer(streamUrl, (instance) => {
    instance.loop = false;
    instance.timeUpdateEventInterval = 0.5;
    instance.playbackRate = playbackRate;
  });

  useEffect(() => {
    onTimeChangeRef.current = onTimeChange;
  }, [onTimeChange]);

  useEventListener(player, "timeUpdate", ({ currentTime }) => {
    onTimeChangeRef.current(currentTime ?? 0);
  });

  useEventListener(player, "playToEnd", onPlayToEnd);
  useEventListener(player, "sourceLoad", ({ duration }) => {
    if (Number.isFinite(duration) && duration > 0) {
      onDurationChange(duration);
    }
  });

  useEffect(() => {
    if (!isStarted) {
      playbackCommandRef.current = "idle";
      return;
    }
    const nextCommand = isPlaying ? "play" : "pause";
    if (playbackCommandRef.current === nextCommand) {
      return;
    }
    playbackCommandRef.current = nextCommand;
    ignoreReleasedPlayerError(() => {
      if (nextCommand === "play") {
        player.play();
      } else {
        player.pause();
      }
    });
  }, [isPlaying, isStarted, player]);

  useEffect(() => {
    ignoreReleasedPlayerError(() => {
      player.playbackRate = playbackRate;
    });
  }, [playbackRate, player]);

  useEffect(() => {
    if (seekRequest && seekRequest.id !== lastHandledSeekIdRef.current) {
      lastHandledSeekIdRef.current = seekRequest.id;
      ignoreReleasedPlayerError(() => {
        player.currentTime = seekRequest.time;
      });
      onTimeChangeRef.current(seekRequest.time);
      onSeekHandled();
    }
  }, [onSeekHandled, player, seekRequest]);

  return (
    <View style={styles.root}>
      <VideoView
        style={styles.video}
        player={player}
        nativeControls={false}
        contentFit="cover"
        fullscreenOptions={DISABLED_FULLSCREEN_OPTIONS}
        allowsPictureInPicture={false}
        surfaceType={VIDEO_SURFACE_TYPE}
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

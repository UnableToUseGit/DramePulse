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
import { SeekRequest, VideoStage } from "./VideoStage";

export function PlayerPage({
  video,
  isActive,
  height,
  hasStartedFeed,
  selectedPresentationType,
  onChangePresentationType,
  onStartFeed
}: {
  video: PlayerVideo;
  isActive: boolean;
  height: number;
  hasStartedFeed: boolean;
  selectedPresentationType: InteractionPresentationType;
  onChangePresentationType: (type: InteractionPresentationType) => void;
  onStartFeed: () => void;
}) {
  const [danmaku, setDanmaku] = useState<DanmakuItem[]>([]);
  const [danmakuState, setDanmakuState] = useState<"loading" | "ready" | "error">("loading");
  const [currentTime, setCurrentTime] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [exampleDismissed, setExampleDismissed] = useState(false);
  const previousTimeRef = useRef(0);
  const playbackMode = useMemo(
    () => getFeedPlaybackMode({ hasStartedFeed, isActive }),
    [hasStartedFeed, isActive]
  );
  const canPlay = isActive && isStarted && isPlaying;

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
      return;
    }
    setCurrentTime(0);
    setIsStarted(playbackMode.shouldAutoStart);
    setIsPlaying(playbackMode.shouldAutoStart);
    setSeekRequest({ id: Date.now(), time: 0 });
    setSeekVersion((version) => version + 1);
    setExampleDismissed(false);
    previousTimeRef.current = 0;
  }, [isActive, playbackMode.shouldAutoStart, video.videoId]);

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
        setCurrentTime(time);
      }
    },
    [isActive]
  );

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

  const handleSeekCommit = useCallback(
    (time: number) => {
      if (!isActive) {
        return;
      }
      setCurrentTime(time);
      previousTimeRef.current = time;
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

  return (
    <View style={[styles.root, { height }]}>
      <VideoStage
        isStarted={isStarted}
        isPlaying={canPlay}
        seekRequest={seekRequest}
        onStart={handleStart}
        onTimeChange={handleTimeChange}
        showStartEntry={playbackMode.shouldShowStartEntry}
        streamUrl={video.streamUrl}
      />
      {isActive && isStarted && danmakuState === "ready" ? (
        <DanmakuLayer currentTime={currentTime} danmaku={danmaku} isPlaying={canPlay} seekVersion={seekVersion} />
      ) : null}
      {isActive && isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
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
        seriesName={video.seriesName}
        title={video.title}
        episodeLabel={video.episodeLabel}
      />
      {ENABLE_INTERACTION_LAB && isActive ? (
        <InteractionLabControls selectedType={selectedPresentationType} onChange={onChangePresentationType} />
      ) : null}
      <PlayerControls currentTime={currentTime} duration={video.duration} onSeekCommit={handleSeekCommit} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    backgroundColor: "#050505",
    overflow: "hidden"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject
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

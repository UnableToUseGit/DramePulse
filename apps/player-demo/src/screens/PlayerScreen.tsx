import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { DanmakuLayer } from "../components/DanmakuLayer";
import { PlaybackHint } from "../components/PlaybackHint";
import { PlayerControls } from "../components/PlayerControls";
import { PlayerChrome } from "../components/PlayerChrome";
import { SeekRequest, VideoStage } from "../components/VideoStage";
import { API_BASE_URL, ENABLE_INTERACTION_LAB } from "../config";
import { loadPlayerData, PlayerData } from "../domain/playerApi";
import { DEFAULT_INTERACTION_EXAMPLE } from "../interaction-examples/examples";
import { InteractionExampleRenderer } from "../interaction-examples/InteractionExampleRenderer";
import { InteractionLabControls } from "../interaction-examples/InteractionLabControls";
import { shouldResetExample, shouldShowExample } from "../interaction-examples/trigger";
import type { InteractionPresentationType } from "../interaction-examples/types";
import { colors, radii, spacing } from "../theme";

export function PlayerScreen() {
  const [playerData, setPlayerData] = useState<PlayerData | undefined>();
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const [currentTime, setCurrentTime] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [selectedPresentationType, setSelectedPresentationType] = useState<InteractionPresentationType>("poll_bar");
  const [exampleDismissed, setExampleDismissed] = useState(false);
  const previousTimeRef = useRef(0);

  const fetchPlayerData = useCallback(async () => {
    setLoadState("loading");
    setLoadError(undefined);
    try {
      const data = await loadPlayerData({ apiBaseUrl: API_BASE_URL });
      setPlayerData(data);
      setLoadState("ready");
      setCurrentTime(0);
      setIsStarted(false);
      setIsPlaying(false);
      setSeekRequest(undefined);
      setSeekVersion((version) => version + 1);
      setExampleDismissed(false);
      previousTimeRef.current = 0;
    } catch (error: unknown) {
      setLoadError(error instanceof Error ? error.message : "无法连接后端服务");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadState("loading");
    setLoadError(undefined);
    loadPlayerData({ apiBaseUrl: API_BASE_URL })
      .then((data) => {
        if (!cancelled) {
          setPlayerData(data);
          setLoadState("ready");
          setExampleDismissed(false);
          previousTimeRef.current = 0;
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "无法连接后端服务");
          setLoadState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleTimeChange = useCallback((time: number) => {
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
  }, []);

  const handleStart = useCallback(() => {
    setIsStarted(true);
    setIsPlaying(true);
  }, []);

  const handleTogglePlay = useCallback(() => {
    if (!isStarted) {
      handleStart();
      return;
    }
    setIsPlaying((playing) => !playing);
  }, [handleStart, isStarted]);

  const handleSeekCommit = useCallback((time: number) => {
    setCurrentTime(time);
    previousTimeRef.current = time;
    if (time < DEFAULT_INTERACTION_EXAMPLE.triggerTimeSec) {
      setExampleDismissed(false);
    }
    setIsStarted(true);
    setSeekVersion((version) => version + 1);
    setSeekRequest({ id: Date.now(), time });
  }, []);

  const handleChangePresentationType = useCallback((type: InteractionPresentationType) => {
    setSelectedPresentationType(type);
    setExampleDismissed(false);
  }, []);

  const handleDismissExample = useCallback(() => {
    setExampleDismissed(true);
  }, []);

  const isExampleVisible = shouldShowExample({
    example: DEFAULT_INTERACTION_EXAMPLE,
    currentTime,
    isStarted,
    dismissed: exampleDismissed,
    presentationType: selectedPresentationType
  });

  if (loadState === "loading") {
    return (
      <View style={[styles.root, styles.centerState]}>
        <Text style={styles.stateTitle}>正在连接后端视频源</Text>
        <Text style={styles.stateText}>GET {API_BASE_URL}/api/videos</Text>
      </View>
    );
  }

  if (loadState === "error" || !playerData) {
    return (
      <View style={[styles.root, styles.centerState]}>
        <Text style={styles.stateTitle}>无法加载播放器数据</Text>
        <Text style={styles.stateText}>{loadError ?? "请确认 services/api 已启动"}</Text>
        <Pressable style={styles.retryButton} onPress={fetchPlayerData}>
          <Text style={styles.retryText}>重试</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <VideoStage
        isStarted={isStarted}
        isPlaying={isPlaying}
        seekRequest={seekRequest}
        onStart={handleStart}
        onTimeChange={handleTimeChange}
        streamUrl={playerData.video.streamUrl}
      />
      {isStarted ? (
        <DanmakuLayer
          currentTime={currentTime}
          danmaku={playerData.danmaku}
          isPlaying={isPlaying}
          seekVersion={seekVersion}
        />
      ) : null}
      {isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
      <PlaybackHint isStarted={isStarted} isPlaying={isPlaying} />
      <InteractionExampleRenderer
        example={DEFAULT_INTERACTION_EXAMPLE}
        presentationType={selectedPresentationType}
        visible={isExampleVisible}
        onDismiss={handleDismissExample}
      />
      <PlayerChrome
        onToggleDebug={() => undefined}
        seriesName={playerData.video.seriesName}
        title={playerData.video.title}
        episodeLabel={playerData.video.episodeLabel}
      />
      {ENABLE_INTERACTION_LAB ? (
        <InteractionLabControls selectedType={selectedPresentationType} onChange={handleChangePresentationType} />
      ) : null}
      <PlayerControls
        currentTime={currentTime}
        duration={playerData.video.duration}
        onSeekCommit={handleSeekCommit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#050505"
  },
  centerState: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl
  },
  stateTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "900",
    textAlign: "center"
  },
  stateText: {
    marginTop: spacing.sm,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    textAlign: "center"
  },
  retryButton: {
    marginTop: spacing.lg,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: colors.accent
  },
  retryText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "900"
  },
  tapLayer: {
    ...StyleSheet.absoluteFillObject
  }
});

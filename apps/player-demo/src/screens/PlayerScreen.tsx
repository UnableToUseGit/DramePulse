import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { DanmakuLayer } from "../components/DanmakuLayer";
import { InteractionPollBar } from "../components/InteractionPollBar";
import { PlaybackHint } from "../components/PlaybackHint";
import { PlayerControls } from "../components/PlayerControls";
import { PlayerChrome } from "../components/PlayerChrome";
import { SeekRequest, VideoStage } from "../components/VideoStage";
import { API_BASE_URL } from "../config";
import { createInitialStats, createUserEvent, updateStats } from "../domain/events";
import { findActiveInteractionPlan } from "../domain/interactionScheduler";
import { loadPlayerData, PlayerData } from "../domain/playerApi";
import type { InteractionOption, InteractionPlan, InteractionStats, UserEvent } from "../domain/types";
import { colors, radii, spacing } from "../theme";

const POLL_IDLE_TTL_SEC = 3;
const POLL_RESULT_TTL_SEC = 2;

export function PlayerScreen() {
  const [playerData, setPlayerData] = useState<PlayerData | undefined>();
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<string | undefined>();
  const [currentTime, setCurrentTime] = useState(0);
  const [isStarted, setIsStarted] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [seekRequest, setSeekRequest] = useState<SeekRequest | undefined>();
  const [seekVersion, setSeekVersion] = useState(0);
  const [activePlan, setActivePlan] = useState<InteractionPlan | undefined>();
  const [selectedOption, setSelectedOption] = useState<InteractionOption | undefined>();
  const [activePlanShownAt, setActivePlanShownAt] = useState<number | undefined>();
  const [selectedAt, setSelectedAt] = useState<number | undefined>();
  const [completedInteractionIds, setCompletedInteractionIds] = useState<Set<string>>(() => new Set());
  const [events, setEvents] = useState<UserEvent[]>([]);
  const [stats, setStats] = useState<InteractionStats>(() => createInitialStats());
  const interactionPlans = useMemo<InteractionPlan[]>(() => [], []);

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

  const appendEvent = useCallback((event: UserEvent) => {
    setEvents((current) => [...current, event]);
    setStats((current) => updateStats(current, event));
  }, []);

  const handleTimeChange = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  useEffect(() => {
    if (!isStarted) {
      return;
    }

    if (activePlan) {
      if (currentTime < activePlan.trigger_time) {
        setActivePlan(undefined);
        setSelectedOption(undefined);
        setActivePlanShownAt(undefined);
        setSelectedAt(undefined);
        return;
      }
      if (selectedOption) {
        if (selectedAt !== undefined && currentTime - selectedAt >= POLL_RESULT_TTL_SEC) {
          setActivePlan(undefined);
          setSelectedOption(undefined);
          setActivePlanShownAt(undefined);
          setSelectedAt(undefined);
        }
        return;
      }
      if (activePlanShownAt !== undefined && currentTime - activePlanShownAt >= POLL_IDLE_TTL_SEC) {
        appendEvent(
          createUserEvent({
            eventType: "interaction_dismiss",
            plan: activePlan,
            clientTime: currentTime
          })
        );
        setCompletedInteractionIds((current) => new Set(current).add(activePlan.interaction_id));
        setActivePlan(undefined);
        setSelectedOption(undefined);
        setActivePlanShownAt(undefined);
        setSelectedAt(undefined);
      }
      return;
    }

    const nextPlan = findActiveInteractionPlan({
      plans: interactionPlans,
      currentTime,
      completedIds: completedInteractionIds
    });
    if (!nextPlan) {
      return;
    }

    setActivePlan(nextPlan);
    setSelectedOption(undefined);
    setActivePlanShownAt(currentTime);
    setSelectedAt(undefined);
    appendEvent(
      createUserEvent({
        eventType: "interaction_exposure",
        plan: nextPlan,
        clientTime: currentTime
      })
    );
  }, [
    activePlan,
    activePlanShownAt,
    appendEvent,
    completedInteractionIds,
    currentTime,
    interactionPlans,
    isStarted,
    selectedAt,
    selectedOption
  ]);

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
    setIsStarted(true);
    setSeekVersion((version) => version + 1);
    setSeekRequest({ id: Date.now(), time });
  }, []);

  const handleSelectOption = useCallback(
    (option: InteractionOption) => {
      if (!activePlan || selectedOption) {
        return;
      }
      setSelectedOption(option);
      setSelectedAt(currentTime);
      setCompletedInteractionIds((current) => new Set(current).add(activePlan.interaction_id));
      appendEvent(
        createUserEvent({
          eventType: "option_click",
          plan: activePlan,
          optionId: option.option_id,
          clientTime: currentTime
        })
      );
      appendEvent(
        createUserEvent({
          eventType: "feedback_shown",
          plan: activePlan,
          optionId: option.option_id,
          clientTime: currentTime
        })
      );
    },
    [activePlan, appendEvent, currentTime, selectedOption]
  );

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
      <InteractionPollBar plan={activePlan} selectedOption={selectedOption} onSelect={handleSelectOption} />
      <PlayerChrome
        onToggleDebug={() => undefined}
        seriesName={playerData.video.seriesName}
        title={playerData.video.title}
        episodeLabel={playerData.video.episodeLabel}
      />
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

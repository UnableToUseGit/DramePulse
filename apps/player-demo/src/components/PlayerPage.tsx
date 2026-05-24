import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { createInitialStats, createUserEvent, updateStats } from "../domain/events";
import { findActiveInteractionPlan } from "../domain/interactionScheduler";
import { getFeedPlaybackMode } from "../domain/playerFeed";
import { loadVideoDanmaku, PlayerVideo } from "../domain/playerApi";
import type { DanmakuItem, InteractionOption, InteractionPlan, InteractionStats, UserEvent } from "../domain/types";
import { colors, spacing } from "../theme";
import { DanmakuLayer } from "./DanmakuLayer";
import { InteractionPollBar } from "./InteractionPollBar";
import { PlaybackHint } from "./PlaybackHint";
import { PlayerChrome } from "./PlayerChrome";
import { PlayerControls } from "./PlayerControls";
import { SeekRequest, VideoStage } from "./VideoStage";

const POLL_IDLE_TTL_SEC = 3;
const POLL_RESULT_TTL_SEC = 2;

export function PlayerPage({
  video,
  isActive,
  height,
  hasStartedFeed,
  onStartFeed
}: {
  video: PlayerVideo;
  isActive: boolean;
  height: number;
  hasStartedFeed: boolean;
  onStartFeed: () => void;
}) {
  const [danmaku, setDanmaku] = useState<DanmakuItem[]>([]);
  const [danmakuState, setDanmakuState] = useState<"loading" | "ready" | "error">("loading");
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
  const [, setEvents] = useState<UserEvent[]>([]);
  const [, setStats] = useState<InteractionStats>(() => createInitialStats());
  const interactionPlans = useMemo<InteractionPlan[]>(() => [], []);
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
    setActivePlan(undefined);
    setSelectedOption(undefined);
    setActivePlanShownAt(undefined);
    setSelectedAt(undefined);
    setCompletedInteractionIds(new Set());
  }, [isActive, playbackMode.shouldAutoStart, video.videoId]);

  useEffect(() => {
    if (playbackMode.shouldAutoStart && !isStarted) {
      setIsStarted(true);
      setIsPlaying(true);
    }
  }, [isStarted, playbackMode.shouldAutoStart]);

  const appendEvent = useCallback((event: UserEvent) => {
    setEvents((current) => [...current, event]);
    setStats((current) => updateStats(current, event));
  }, []);

  const handleTimeChange = useCallback(
    (time: number) => {
      if (isActive) {
        setCurrentTime(time);
      }
    },
    [isActive]
  );

  useEffect(() => {
    if (!isActive || !isStarted) {
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
    isActive,
    isStarted,
    selectedAt,
    selectedOption
  ]);

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
      setIsStarted(true);
      setSeekVersion((version) => version + 1);
      setSeekRequest({ id: Date.now(), time });
    },
    [isActive]
  );

  const handleSelectOption = useCallback(
    (option: InteractionOption) => {
      if (!isActive || !activePlan || selectedOption) {
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
    [activePlan, appendEvent, currentTime, isActive, selectedOption]
  );

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
      <InteractionPollBar plan={activePlan} selectedOption={selectedOption} onSelect={handleSelectOption} />
      <PlayerChrome
        onToggleDebug={() => undefined}
        seriesName={video.seriesName}
        title={video.title}
        episodeLabel={video.episodeLabel}
      />
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

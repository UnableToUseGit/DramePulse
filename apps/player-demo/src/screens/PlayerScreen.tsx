import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { DanmakuLayer } from "../components/DanmakuLayer";
import { InteractionPollBar } from "../components/InteractionPollBar";
import { PlaybackHint } from "../components/PlaybackHint";
import { PlayerControls } from "../components/PlayerControls";
import { PlayerChrome } from "../components/PlayerChrome";
import { SeekRequest, VideoStage } from "../components/VideoStage";
import { createInitialStats, createUserEvent, updateStats } from "../domain/events";
import { getDemoFixtures } from "../domain/fixtures";
import { findActiveInteractionPlan } from "../domain/interactionScheduler";
import type { InteractionOption, InteractionPlan, InteractionStats, UserEvent } from "../domain/types";
import { fetchFirstVideoStreamUrl } from "../domain/videos";

const POLL_IDLE_TTL_SEC = 3;
const POLL_RESULT_TTL_SEC = 2;

export function PlayerScreen() {
  const fixtures = useMemo(() => getDemoFixtures(), []);
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
  const [videoUri, setVideoUri] = useState<string | undefined>();

  const appendEvent = useCallback((event: UserEvent) => {
    setEvents((current) => [...current, event]);
    setStats((current) => updateStats(current, event));
  }, []);

  const handleTimeChange = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  useEffect(() => {
    let isMounted = true;
    fetchFirstVideoStreamUrl()
      .then((streamUrl) => {
        if (isMounted) {
          setVideoUri(streamUrl);
        }
      })
      .catch(() => {
        if (isMounted) {
          setVideoUri(undefined);
        }
      });
    return () => {
      isMounted = false;
    };
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
      plans: fixtures.interactionPlans,
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
    fixtures.interactionPlans,
    isStarted,
    selectedAt,
    selectedOption
  ]);

  const handleStart = useCallback(() => {
    if (!videoUri) {
      return;
    }
    setIsStarted(true);
    setIsPlaying(true);
  }, [videoUri]);

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

  return (
    <View style={styles.root}>
      <VideoStage
        isStarted={isStarted}
        isPlaying={isPlaying}
        seekRequest={seekRequest}
        onStart={handleStart}
        onTimeChange={handleTimeChange}
        videoUri={videoUri}
      />
      {isStarted ? (
        <DanmakuLayer
          currentTime={currentTime}
          danmaku={fixtures.danmaku}
          isPlaying={isPlaying}
          seekVersion={seekVersion}
        />
      ) : null}
      {isStarted ? <Pressable style={styles.tapLayer} onPress={handleTogglePlay} /> : null}
      <PlaybackHint isStarted={isStarted} isPlaying={isPlaying} />
      <InteractionPollBar plan={activePlan} selectedOption={selectedOption} onSelect={handleSelectOption} />
      <PlayerChrome onToggleDebug={() => undefined} />
      <PlayerControls
        currentTime={currentTime}
        duration={120}
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
  tapLayer: {
    ...StyleSheet.absoluteFillObject
  }
});

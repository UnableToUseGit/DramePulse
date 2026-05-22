import { useCallback, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { DanmakuLayer } from "../components/DanmakuLayer";
import { DebugPanel } from "../components/DebugPanel";
import { FeedbackBurst } from "../components/FeedbackBurst";
import { InteractionPollBar } from "../components/InteractionPollBar";
import { PlayerChrome } from "../components/PlayerChrome";
import { VideoStage } from "../components/VideoStage";
import { createInitialStats, createUserEvent, updateStats } from "../domain/events";
import { getDemoFixtures } from "../domain/fixtures";
import type { InteractionOption, InteractionPlan, InteractionStats, UserEvent } from "../domain/types";

export function PlayerScreen() {
  const fixtures = useMemo(() => getDemoFixtures(), []);
  const [currentTime, setCurrentTime] = useState(0);
  const [debugVisible, setDebugVisible] = useState(false);
  const [activePlan, setActivePlan] = useState<InteractionPlan | undefined>();
  const [selectedOption, setSelectedOption] = useState<InteractionOption | undefined>();
  const [triggeredIds, setTriggeredIds] = useState<Set<string>>(() => new Set());
  const [events, setEvents] = useState<UserEvent[]>([]);
  const [stats, setStats] = useState<InteractionStats>(() => createInitialStats());

  const appendEvent = useCallback((event: UserEvent) => {
    setEvents((current) => [...current, event]);
    setStats((current) => updateStats(current, event));
  }, []);

  const handleTimeChange = useCallback(
    (time: number) => {
      setCurrentTime(time);
      const nextPlan = fixtures.interactionPlans.find(
        (plan) => time >= plan.trigger_time && time <= plan.expire_time && !triggeredIds.has(plan.interaction_id)
      );
      if (!nextPlan) {
        if (activePlan && !selectedOption && time > activePlan.expire_time) {
          appendEvent(
            createUserEvent({
              eventType: "interaction_dismiss",
              plan: activePlan,
              clientTime: time
            })
          );
          setTriggeredIds((current) => new Set(current).add(activePlan.interaction_id));
          setActivePlan(undefined);
        }
        return;
      }

      setActivePlan(nextPlan);
      setSelectedOption(undefined);
      setTriggeredIds((current) => new Set(current).add(nextPlan.interaction_id));
      appendEvent(
        createUserEvent({
          eventType: "interaction_exposure",
          plan: nextPlan,
          clientTime: time
        })
      );
    },
    [activePlan, appendEvent, fixtures.interactionPlans, selectedOption, triggeredIds]
  );

  const handleSelect = useCallback(
    (option: InteractionOption) => {
      if (!activePlan || selectedOption) {
        return;
      }
      setSelectedOption(option);
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
      <VideoStage onTimeChange={handleTimeChange} />
      <DanmakuLayer currentTime={currentTime} danmaku={fixtures.danmaku} />
      <FeedbackBurst selectedOption={selectedOption} />
      <InteractionPollBar plan={activePlan} selectedOption={selectedOption} onSelect={handleSelect} />
      <PlayerChrome onToggleDebug={() => setDebugVisible((visible) => !visible)} />
      <DebugPanel
        visible={debugVisible}
        currentTime={currentTime}
        activePlan={activePlan}
        events={events}
        stats={stats}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#050505"
  }
});

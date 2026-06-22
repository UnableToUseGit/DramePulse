import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { INNER_VOICE_DANMAKU_CUES } from "./cues";
import { InnerVoicePrompt } from "./InnerVoicePrompt";
import { getActiveInnerVoiceCue, getVisibleInnerVoiceCue, shouldResetInnerVoiceCue } from "./scheduler";
import type { InnerVoiceDanmakuCue } from "./types";

export function InnerVoiceDanmakuExample({
  currentTime,
  isActive,
  onDismiss,
  onGestureActiveChange,
  onSend,
  showImmediately = false
}: {
  currentTime: number;
  isActive: boolean;
  onDismiss: () => void;
  onGestureActiveChange: (active: boolean) => void;
  onSend: (cue: InnerVoiceDanmakuCue) => void;
  showImmediately?: boolean;
}) {
  const [completedCueIds, setCompletedCueIds] = useState<Set<string>>(() => new Set());
  const [launchingCue, setLaunchingCue] = useState<InnerVoiceDanmakuCue | undefined>();
  const previousTimeRef = useRef(currentTime);
  const activeCue = useMemo(
    () =>
      isActive
        ? showImmediately && INNER_VOICE_DANMAKU_CUES[0] && !completedCueIds.has(INNER_VOICE_DANMAKU_CUES[0].cueId)
          ? INNER_VOICE_DANMAKU_CUES[0]
          : getActiveInnerVoiceCue({
            cues: INNER_VOICE_DANMAKU_CUES,
            currentTime,
            completedCueIds
          })
        : undefined,
    [completedCueIds, currentTime, isActive, showImmediately]
  );

  const visibleCue = getVisibleInnerVoiceCue({ activeCue, launchingCue });

  const handleCueSend = useCallback(
    (cue: InnerVoiceDanmakuCue) => {
      setLaunchingCue(cue);
      onSend(cue);
      onDismiss();
    },
    [onDismiss, onSend]
  );

  const handleExitComplete = useCallback((cue: InnerVoiceDanmakuCue) => {
    setCompletedCueIds((ids) => new Set(ids).add(cue.cueId));
    setLaunchingCue((current) => (current?.cueId === cue.cueId ? undefined : current));
  }, []);

  useEffect(() => {
    const previousTime = previousTimeRef.current;
    previousTimeRef.current = currentTime;
    if (
      shouldResetInnerVoiceCue({
        previousTime,
        currentTime,
        firstTriggerTime: INNER_VOICE_DANMAKU_CUES[0]?.triggerTime ?? 0
      })
    ) {
      setCompletedCueIds(new Set());
      setLaunchingCue(undefined);
    }
  }, [currentTime]);

  return (
    <>
      {visibleCue ? (
        <InnerVoicePrompt
          key={visibleCue.cueId}
          cue={visibleCue}
          onSend={handleCueSend}
          onGestureActiveChange={onGestureActiveChange}
          onExitComplete={handleExitComplete}
        />
      ) : null}
    </>
  );
}

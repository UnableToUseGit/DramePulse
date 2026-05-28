import { useCallback, useEffect, useState } from "react";
import type { InteractionExample, InteractionPresentationType } from "../interaction-examples/types";
import { shouldShowExample } from "../interaction-examples/trigger";

export function useInteractionExampleState({
  currentTime,
  example,
  isActive,
  isStarted,
  presentationType,
  resetKey
}: {
  currentTime: number;
  example: InteractionExample;
  isActive: boolean;
  isStarted: boolean;
  presentationType: InteractionPresentationType;
  resetKey: string;
}) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setDismissed(false);
  }, [presentationType, resetKey]);

  const reset = useCallback(() => {
    setDismissed(false);
  }, []);

  const dismiss = useCallback(() => {
    setDismissed(true);
  }, []);

  const visible = shouldShowExample({
    example,
    currentTime,
    isStarted: isActive && isStarted,
    dismissed,
    presentationType
  });

  return { dismiss, dismissed, reset, visible };
}

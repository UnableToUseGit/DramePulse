export type ResonancePresencePhase = "hidden" | "entering" | "visible" | "exiting";

export type ResonancePresenceState = {
  phase: ResonancePresencePhase;
  renderedCueId?: string;
};

export type ResonancePresenceEvent =
  | { type: "cue_present"; cueId: string }
  | { type: "cue_absent" }
  | { type: "enter_complete" }
  | { type: "exit_complete" };

export function createHiddenPresenceState(): ResonancePresenceState {
  return { phase: "hidden" };
}

export function reducePresenceState(
  state: ResonancePresenceState,
  event: ResonancePresenceEvent
): ResonancePresenceState {
  if (event.type === "cue_present") {
    if (state.renderedCueId === event.cueId && state.phase !== "hidden") {
      return state.phase === "exiting" ? { phase: "entering", renderedCueId: event.cueId } : state;
    }
    return { phase: "entering", renderedCueId: event.cueId };
  }

  if (event.type === "cue_absent") {
    return state.renderedCueId ? { phase: "exiting", renderedCueId: state.renderedCueId } : state;
  }

  if (event.type === "enter_complete") {
    return state.renderedCueId ? { phase: "visible", renderedCueId: state.renderedCueId } : createHiddenPresenceState();
  }

  if (event.type === "exit_complete") {
    return createHiddenPresenceState();
  }

  return state;
}

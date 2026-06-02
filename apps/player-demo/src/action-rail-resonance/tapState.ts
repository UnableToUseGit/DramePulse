export type ResonanceTapPhase = "idle" | "joined" | "releasing";

export type ResonanceTapAction = "none" | "join" | "release";

export type ResonanceTapState = {
  phase: ResonanceTapPhase;
  tapCount: number;
  releaseCount: number;
  action: ResonanceTapAction;
};

export function createInitialResonanceTapState(): ResonanceTapState {
  return {
    phase: "idle",
    tapCount: 0,
    releaseCount: 0,
    action: "none"
  };
}

export function reduceResonanceTap(state: ResonanceTapState): ResonanceTapState {
  const tapCount = state.tapCount + 1;
  if (state.phase === "idle") {
    return {
      phase: "joined",
      tapCount,
      releaseCount: 0,
      action: "join"
    };
  }
  return {
    phase: "releasing",
    tapCount,
    releaseCount: state.releaseCount + 1,
    action: "release"
  };
}

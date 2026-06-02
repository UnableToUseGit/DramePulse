import { createHiddenPresenceState, reducePresenceState } from "../presence";

describe("action rail resonance presence", () => {
  it("enters when a cue becomes available", () => {
    const state = reducePresenceState(createHiddenPresenceState(), { type: "cue_present", cueId: "cue-1" });

    expect(state.phase).toBe("entering");
    expect(state.renderedCueId).toBe("cue-1");
  });

  it("becomes visible after enter animation finishes", () => {
    const entering = reducePresenceState(createHiddenPresenceState(), { type: "cue_present", cueId: "cue-1" });
    const visible = reducePresenceState(entering, { type: "enter_complete" });

    expect(visible.phase).toBe("visible");
    expect(visible.renderedCueId).toBe("cue-1");
  });

  it("keeps rendering while exiting after the cue disappears", () => {
    const visible = { phase: "visible" as const, renderedCueId: "cue-1" };
    const exiting = reducePresenceState(visible, { type: "cue_absent" });

    expect(exiting.phase).toBe("exiting");
    expect(exiting.renderedCueId).toBe("cue-1");
  });

  it("hides only after exit animation finishes", () => {
    const exiting = { phase: "exiting" as const, renderedCueId: "cue-1" };
    const hidden = reducePresenceState(exiting, { type: "exit_complete" });

    expect(hidden.phase).toBe("hidden");
    expect(hidden.renderedCueId).toBeUndefined();
  });
});

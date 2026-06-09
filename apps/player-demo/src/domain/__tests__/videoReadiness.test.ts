import {
  createVideoReadinessState,
  reduceVideoReadinessState
} from "../videoReadiness";

describe("videoReadiness", () => {
  it("does not become ready from the first rendered frame alone", () => {
    const state = reduceVideoReadinessState(createVideoReadinessState(0), {
      type: "first_frame_render"
    });

    expect(state.isReady).toBe(false);
  });

  it("does not become ready until playback is moving after the first frame", () => {
    const firstFrame = reduceVideoReadinessState(createVideoReadinessState(0), {
      type: "first_frame_render"
    });
    const playing = reduceVideoReadinessState(firstFrame, {
      type: "playing_change",
      isPlaying: true
    });

    expect(playing.isReady).toBe(false);

    const stillAtStart = reduceVideoReadinessState(playing, {
      type: "time_update",
      currentTime: 0.02
    });

    expect(stillAtStart.isReady).toBe(false);

    const advanced = reduceVideoReadinessState(stillAtStart, {
      type: "time_update",
      currentTime: 0.35
    });

    expect(advanced.isReady).toBe(true);
  });

  it("respects resume time when deciding whether playback has moved", () => {
    const initial = createVideoReadinessState(42);
    const firstFrame = reduceVideoReadinessState(initial, { type: "first_frame_render" });
    const playing = reduceVideoReadinessState(firstFrame, { type: "playing_change", isPlaying: true });

    expect(reduceVideoReadinessState(playing, { type: "time_update", currentTime: 42.03 }).isReady).toBe(false);
    expect(reduceVideoReadinessState(playing, { type: "time_update", currentTime: 42.3 }).isReady).toBe(true);
  });
});

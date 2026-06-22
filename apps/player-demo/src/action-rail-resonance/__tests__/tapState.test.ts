import { createInitialResonanceTapState, reduceResonanceTap } from "../tapState";

describe("action rail resonance tap state", () => {
  it("treats the first tap as joining the public reaction", () => {
    const state = reduceResonanceTap(createInitialResonanceTapState());

    expect(state.phase).toBe("joined");
    expect(state.tapCount).toBe(1);
    expect(state.releaseCount).toBe(0);
    expect(state.action).toBe("join");
  });

  it("treats later taps as emotional release combo", () => {
    const joined = reduceResonanceTap(createInitialResonanceTapState());
    const releasing = reduceResonanceTap(joined);

    expect(releasing.phase).toBe("releasing");
    expect(releasing.tapCount).toBe(2);
    expect(releasing.releaseCount).toBe(1);
    expect(releasing.action).toBe("release");
  });

  it("keeps increasing release count without rejoining", () => {
    const state = [1, 2, 3, 4].reduce((current) => reduceResonanceTap(current), createInitialResonanceTapState());

    expect(state.phase).toBe("releasing");
    expect(state.tapCount).toBe(4);
    expect(state.releaseCount).toBe(3);
    expect(state.action).toBe("release");
  });
});

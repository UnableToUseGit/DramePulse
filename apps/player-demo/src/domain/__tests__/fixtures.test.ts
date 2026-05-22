import { getDemoFixtures } from "../fixtures";

describe("getDemoFixtures", () => {
  it("loads sorted danmaku and active danmaku poll plans", () => {
    const fixtures = getDemoFixtures();

    expect(fixtures.videoId).toBe("case1_ep01");
    expect(fixtures.danmaku.length).toBeGreaterThan(0);
    expect(fixtures.interactionPlans.length).toBeGreaterThan(0);
    expect(fixtures.interactionPlans.every((plan) => plan.interaction_type === "danmaku_poll")).toBe(true);
    expect(fixtures.interactionPlans[0].trigger_time).toBeLessThanOrEqual(fixtures.interactionPlans[1].trigger_time);
  });
});

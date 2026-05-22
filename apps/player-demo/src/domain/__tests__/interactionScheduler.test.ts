import { findActiveInteractionPlan } from "../interactionScheduler";
import type { InteractionPlan } from "../types";

const plans: InteractionPlan[] = [
  {
    interaction_id: "i_1",
    highlight_id: "h_1",
    video_id: "case1_ep01",
    trigger_time: 8,
    expire_time: 12,
    interaction_type: "danmaku_poll",
    question: "你怎么看？",
    options: [
      { option_id: "o_1", text: "爽", danmaku_text: "爽", rank: 1 },
      { option_id: "o_2", text: "离谱", danmaku_text: "离谱", rank: 2 }
    ],
    feedback: { type: "poll_result" },
    status: "active"
  },
  {
    interaction_id: "i_2",
    highlight_id: "h_2",
    video_id: "case1_ep01",
    trigger_time: 20,
    expire_time: 25,
    interaction_type: "danmaku_poll",
    question: "值不值？",
    options: [
      { option_id: "o_3", text: "值", danmaku_text: "值", rank: 1 },
      { option_id: "o_4", text: "不值", danmaku_text: "不值", rank: 2 }
    ],
    feedback: { type: "poll_result" },
    status: "active"
  }
];

describe("findActiveInteractionPlan", () => {
  it("returns a plan at or after trigger time without depending on expire time", () => {
    expect(findActiveInteractionPlan({ plans, currentTime: 9, completedIds: new Set() })?.interaction_id).toBe("i_1");
    expect(findActiveInteractionPlan({ plans, currentTime: 13, completedIds: new Set() })?.interaction_id).toBe("i_1");
  });

  it("does not return completed plans", () => {
    expect(findActiveInteractionPlan({ plans, currentTime: 9, completedIds: new Set(["i_1"]) })).toBeUndefined();
  });
});

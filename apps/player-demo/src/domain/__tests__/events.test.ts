import { createUserEvent, updateStats } from "../events";
import type { InteractionPlan } from "../types";

const plan: InteractionPlan = {
  interaction_id: "i_h_case1_ep01_001",
  highlight_id: "h_case1_ep01_001",
  video_id: "case1_ep01",
  trigger_time: 8.96,
  expire_time: 12.04,
  interaction_type: "danmaku_poll",
  question: "换你是女主你什么反应？",
  options: [
    { option_id: "o_1", text: "直接懵了", danmaku_text: "我人直接傻了啊！", rank: 1, base_score: 0.8 }
  ],
  feedback: {
    type: "poll_result",
    show_ratio: true,
    show_resonance_text: true,
    resonance_text_template: "你和 {ratio}% 的观众一样选择了「{option}」"
  },
  display_position: "subtitle_safe_area",
  status: "active"
};

describe("event helpers", () => {
  it("creates user events aligned with the contract", () => {
    const event = createUserEvent({
      eventType: "option_click",
      plan,
      optionId: "o_1",
      clientTime: 9.2,
      nowSeconds: 1779370000
    });

    expect(event.event_type).toBe("option_click");
    expect(event.user_id).toBe("u_demo_001");
    expect(event.video_id).toBe("case1_ep01");
    expect(event.highlight_id).toBe("h_case1_ep01_001");
    expect(event.interaction_id).toBe("i_h_case1_ep01_001");
    expect(event.option_id).toBe("o_1");
    expect(event.client_time).toBe(9.2);
    expect(event.timestamp).toBe(1779370000);
  });

  it("updates local stats for exposure, click, feedback, and dismiss", () => {
    let stats = updateStats(
      undefined,
      createUserEvent({ eventType: "interaction_exposure", plan, clientTime: 9, nowSeconds: 1 })
    );
    stats = updateStats(
      stats,
      createUserEvent({ eventType: "option_click", plan, optionId: "o_1", clientTime: 9.2, nowSeconds: 2 })
    );
    stats = updateStats(
      stats,
      createUserEvent({ eventType: "feedback_shown", plan, optionId: "o_1", clientTime: 9.5, nowSeconds: 3 })
    );
    stats = updateStats(
      stats,
      createUserEvent({ eventType: "interaction_dismiss", plan, clientTime: 12.1, nowSeconds: 4 })
    );

    expect(stats.exposure_count).toBe(1);
    expect(stats.click_count).toBe(1);
    expect(stats.feedback_shown_count).toBe(1);
    expect(stats.dismiss_count).toBe(1);
    expect(stats.option_click_count.o_1).toBe(1);
    expect(stats.option_click_rate.o_1).toBe(1);
  });
});

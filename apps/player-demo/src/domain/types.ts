export type InteractionEventType =
  | "interaction_exposure"
  | "option_click"
  | "feedback_shown"
  | "interaction_dismiss";

export interface DanmakuItem {
  danmaku_id?: string;
  time_sec: number;
  text: string;
  variant?: "normal" | "inner_voice";
  digg_count?: number;
  score?: number;
}

export interface InteractionOption {
  option_id: string;
  text: string;
  danmaku_text: string;
  rank?: number;
  base_score?: number;
}

export interface InteractionFeedback {
  type: "poll_result" | "resonance_text" | "danmaku_burst" | "none";
  show_ratio?: boolean;
  show_resonance_text?: boolean;
  resonance_text_template?: string;
}

export interface InteractionPlan {
  interaction_id: string;
  highlight_id: string;
  video_id: string;
  trigger_time: number;
  expire_time: number;
  interaction_type: "danmaku_poll";
  question: string;
  options: InteractionOption[];
  feedback: InteractionFeedback;
  display_position?: string;
  status?: "draft" | "active" | "disabled";
}

export interface PlayerFixtures {
  videoId: string;
  danmaku: DanmakuItem[];
  interactionPlans: InteractionPlan[];
}

export interface UserEvent {
  event_type: InteractionEventType;
  user_id: string;
  video_id: string;
  highlight_id: string;
  interaction_id: string;
  option_id?: string;
  client_time: number;
  timestamp: number;
  extra: {
    interaction_type: string;
    device: string;
  };
}

export interface InteractionStats {
  exposure_count: number;
  click_count: number;
  feedback_shown_count: number;
  dismiss_count: number;
  option_click_count: Record<string, number>;
  option_click_rate: Record<string, number>;
}

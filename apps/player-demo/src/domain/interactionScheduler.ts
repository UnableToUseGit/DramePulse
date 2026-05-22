import type { InteractionPlan } from "./types";

export function findActiveInteractionPlan({
  plans,
  currentTime,
  completedIds
}: {
  plans: InteractionPlan[];
  currentTime: number;
  completedIds: Set<string>;
}): InteractionPlan | undefined {
  return plans.find(
    (plan) =>
      plan.status !== "disabled" &&
      !completedIds.has(plan.interaction_id) &&
      currentTime >= plan.trigger_time
  );
}

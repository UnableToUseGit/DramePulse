# Action Rail Resonance Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first frontend version of the right action rail resonance button, so users can tap a high-point emotion count and feel they joined a public reaction.

**Architecture:** Add a focused `action-rail-resonance` module with cue fixtures, scheduler, count formatting, participation logic, and one React Native button component. Render the component from `PlayerActionRail` at the top of the existing right rail, while `PlayerPage` only passes playback time, active state, seek reset, and the selected interaction mode.

**Tech Stack:** React Native, Expo, TypeScript, Jest.

---

### Task 1: Pure Scheduling And Count Logic

**Files:**
- Create: `apps/player-demo/src/action-rail-resonance/types.ts`
- Create: `apps/player-demo/src/action-rail-resonance/scheduler.ts`
- Create: `apps/player-demo/src/action-rail-resonance/formatCount.ts`
- Create: `apps/player-demo/src/action-rail-resonance/__tests__/scheduler.test.ts`
- Create: `apps/player-demo/src/action-rail-resonance/__tests__/formatCount.test.ts`

- [ ] **Step 1: Write failing scheduler tests**

```ts
import {
  getActiveActionRailResonanceCue,
  shouldResetActionRailResonanceCue
} from "../scheduler";
import type { ActionRailResonanceCue } from "../types";

const cues: ActionRailResonanceCue[] = [
  {
    cueId: "resonance_1",
    videoId: "case1_ep01",
    highlightId: "h_1",
    triggerTime: 8,
    durationSec: 5,
    emotionType: "爽点",
    label: "爽到了",
    icon: "flame",
    baseCount: 82000,
    feedbackText: "你也爽到了"
  }
];

describe("action rail resonance scheduler", () => {
  it("returns the active cue inside its display window", () => {
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 8, completedCueIds: new Set() })?.cueId).toBe(
      "resonance_1"
    );
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 12.9, completedCueIds: new Set() })?.cueId).toBe(
      "resonance_1"
    );
  });

  it("does not return cues before trigger, after expiry, or after completion", () => {
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 7.9, completedCueIds: new Set() })).toBeUndefined();
    expect(getActiveActionRailResonanceCue({ cues, currentTime: 13.1, completedCueIds: new Set() })).toBeUndefined();
    expect(
      getActiveActionRailResonanceCue({ cues, currentTime: 9, completedCueIds: new Set(["resonance_1"]) })
    ).toBeUndefined();
  });

  it("resets completed cue memory when seeking before the earliest cue", () => {
    expect(shouldResetActionRailResonanceCue({ previousTime: 20, currentTime: 2, firstTriggerTime: 8 })).toBe(true);
    expect(shouldResetActionRailResonanceCue({ previousTime: 20, currentTime: 10, firstTriggerTime: 8 })).toBe(false);
  });
});
```

- [ ] **Step 2: Write failing count tests**

```ts
import { formatResonanceCount, getParticipatingCount } from "../formatCount";

describe("action rail resonance count formatting", () => {
  it("formats large counts as compact Chinese public counts", () => {
    expect(formatResonanceCount(82000)).toBe("8.2万");
    expect(formatResonanceCount(120000)).toBe("12万");
    expect(formatResonanceCount(6626)).toBe("6626");
  });

  it("increments the displayed count once after participation", () => {
    expect(getParticipatingCount({ baseCount: 82000, hasParticipated: false })).toBe(82000);
    expect(getParticipatingCount({ baseCount: 82000, hasParticipated: true })).toBe(82001);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd apps/player-demo && npm test -- action-rail-resonance`

Expected: FAIL because the module files do not exist yet.

- [ ] **Step 4: Implement minimal pure logic**

Create `types.ts`, `scheduler.ts`, and `formatCount.ts` with the APIs used by the tests.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/player-demo && npm test -- action-rail-resonance`

Expected: PASS.

### Task 2: Button Component And Rail Integration

**Files:**
- Create: `apps/player-demo/src/action-rail-resonance/cues.ts`
- Create: `apps/player-demo/src/action-rail-resonance/ActionRailResonanceButton.tsx`
- Modify: `apps/player-demo/src/components/PlayerActionRail.tsx`
- Modify: `apps/player-demo/src/components/PlayerChrome.tsx`
- Modify: `apps/player-demo/src/components/PlayerPage.tsx`
- Modify: `apps/player-demo/src/interaction-examples/types.ts`
- Modify: `apps/player-demo/src/interaction-examples/trigger.ts`
- Modify: `apps/player-demo/src/interaction-examples/InteractionLabControls.tsx`

- [ ] **Step 1: Add interaction mode**

Add `action_rail_resonance` to the presentation type, label map, and lab controls options.

- [ ] **Step 2: Add fixture cues**

Create local demo cues with emotion type, icon, base count, and feedback text.

- [ ] **Step 3: Implement `ActionRailResonanceButton`**

Render a rail-style icon and count with press feedback, local count bump, burst tap tracking, and a short feedback label.

- [ ] **Step 4: Wire into `PlayerActionRail`**

Insert the resonance button above existing rail items only when `activeCue` is present.

- [ ] **Step 5: Wire active cue state in `PlayerPage`**

Use the scheduler only when the selected presentation type is `action_rail_resonance`, reset completed cue memory on seek back, and mark cues completed on participate or dismiss.

- [ ] **Step 6: Run verification**

Run: `cd apps/player-demo && npm run typecheck`

Run: `cd apps/player-demo && npm test`

Expected: both commands pass.

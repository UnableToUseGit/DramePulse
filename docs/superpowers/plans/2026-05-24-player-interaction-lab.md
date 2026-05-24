# Player Interaction Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frontend-only Interaction Lab to `apps/player-demo` so developers can switch between `Off`, `Poll Bar`, and `Emoji Hold` UI experiments at a fixed playback trigger.

**Architecture:** Keep interaction examples separate from backend `InteractionPlan`. Add lightweight local example types, trigger state helpers, dev-only controls, and two UI presentations. `PlayerScreen` owns playback state and passes time/playback context into an `InteractionExampleRenderer`.

**Tech Stack:** Expo React Native, TypeScript, Jest, existing `StyleSheet` theme tokens.

---

### Task 1: Local Example Model And Trigger Logic

**Files:**
- Create: `apps/player-demo/src/interaction-examples/types.ts`
- Create: `apps/player-demo/src/interaction-examples/examples.ts`
- Create: `apps/player-demo/src/interaction-examples/trigger.ts`
- Test: `apps/player-demo/src/interaction-examples/__tests__/trigger.test.ts`

- [ ] Write failing tests for presentation labels, trigger eligibility, and reset behavior.
- [ ] Run `npm test -- --runTestsByPath src/interaction-examples/__tests__/trigger.test.ts` in `apps/player-demo` and confirm it fails because files are missing.
- [ ] Implement local types, fixed examples, and pure trigger helpers.
- [ ] Run the same test and confirm it passes.

### Task 2: Interaction Lab UI Components

**Files:**
- Create: `apps/player-demo/src/interaction-examples/InteractionLabControls.tsx`
- Create: `apps/player-demo/src/interaction-examples/InteractionExampleRenderer.tsx`
- Create: `apps/player-demo/src/interaction-examples/PollBarExample.tsx`
- Create: `apps/player-demo/src/interaction-examples/EmojiHoldExample.tsx`

- [ ] Create compact dev-only controls for `Off`, `Poll Bar`, and `Emoji Hold`.
- [ ] Create a renderer that maps `none` to null, `poll_bar` to `PollBarExample`, and `emoji_hold` to `EmojiHoldExample`.
- [ ] Implement `PollBarExample` as a local baseline UI with prompt, options, and short result state.
- [ ] Implement `EmojiHoldExample` with long-press visual feedback and release burst state.

### Task 3: PlayerScreen Integration

**Files:**
- Modify: `apps/player-demo/src/config.ts`
- Modify: `apps/player-demo/src/screens/PlayerScreen.tsx`

- [ ] Add `ENABLE_INTERACTION_LAB`.
- [ ] Remove backend interaction-plan scheduling from `PlayerScreen`.
- [ ] Track selected presentation type and example visibility state.
- [ ] Reset the example when seeking before trigger time or changing presentation type.
- [ ] Render lab controls only when enabled.
- [ ] Render example UI only after fixed trigger time and when video has started.

### Task 4: Verification

**Commands:**
- `npm test -- --runTestsByPath src/interaction-examples/__tests__/trigger.test.ts src/domain/__tests__/playerApi.test.ts src/domain/__tests__/danmakuScheduler.test.ts`
- `npm run typecheck`

- [ ] Run focused tests.
- [ ] Run TypeScript typecheck.
- [ ] Review `git diff` to ensure no backend/event reporting code was introduced.

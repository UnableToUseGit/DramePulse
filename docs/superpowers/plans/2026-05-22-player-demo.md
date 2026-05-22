# Player Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Expo mobile player demo that shows a Hongguo-style vertical short drama player with DramePulse's center danmaku poll interaction, local event stream, and debug stats.

**Architecture:** Create a self-contained Expo app in `apps/player-demo/`. Keep data adaptation, event/stat reducers, and presentation components separate so the demo can later swap local fixtures for backend APIs. Use local fixture data copied from the existing sample outputs and render a single `PlayerScreen`.

**Tech Stack:** React Native, Expo, TypeScript, `expo-video`, `@expo/vector-icons`, Jest for pure logic tests, local JSON/media fixtures.

---

### Task 1: Scaffold Expo App

**Files:**
- Create: `apps/player-demo/package.json`
- Create: `apps/player-demo/app.json`
- Create: `apps/player-demo/tsconfig.json`
- Create: `apps/player-demo/babel.config.js`
- Create: `apps/player-demo/jest.config.js`
- Create: `apps/player-demo/App.tsx`
- Create: `apps/player-demo/src/screens/PlayerScreen.tsx`
- Create: `apps/player-demo/assets/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create app metadata and scripts**

Create `apps/player-demo/package.json` with:

```json
{
  "name": "dramepulse-player-demo",
  "version": "0.1.0",
  "private": true,
  "main": "node_modules/expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "typecheck": "tsc --noEmit",
    "test": "jest --runInBand"
  },
  "dependencies": {
    "@expo/vector-icons": "^15.0.2",
    "expo": "~54.0.0",
    "expo-status-bar": "~3.0.8",
    "expo-video": "~3.0.14",
    "react": "19.1.0",
    "react-native": "0.81.5",
    "react-native-svg": "15.12.1"
  },
  "devDependencies": {
    "@types/jest": "^29.5.14",
    "@types/react": "~19.1.10",
    "jest": "^29.7.0",
    "typescript": "~5.9.2"
  }
}
```

- [ ] **Step 2: Add Expo and TypeScript config**

Create `apps/player-demo/app.json` with:

```json
{
  "expo": {
    "name": "DramePulse Player",
    "slug": "dramepulse-player-demo",
    "version": "0.1.0",
    "orientation": "portrait",
    "scheme": "dramepulse",
    "userInterfaceStyle": "dark",
    "ios": {
      "supportsTablet": false
    },
    "android": {
      "edgeToEdgeEnabled": true
    },
    "plugins": [
      "expo-video"
    ]
  }
}
```

Create `apps/player-demo/tsconfig.json` with:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "noEmit": true,
    "resolveJsonModule": true,
    "types": ["jest"]
  },
  "include": ["App.tsx", "src/**/*.ts", "src/**/*.tsx", "src/**/*.json"]
}
```

Create `apps/player-demo/babel.config.js` with:

```js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"]
  };
};
```

Create `apps/player-demo/jest.config.js` with:

```js
module.exports = {
  preset: "jest-expo",
  testMatch: ["**/__tests__/**/*.test.ts"],
  transformIgnorePatterns: [
    "node_modules/(?!((jest-)?react-native|@react-native|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg))"
  ]
};
```

- [ ] **Step 3: Add minimal app entry**

Create `apps/player-demo/App.tsx` with:

```tsx
import { StatusBar } from "expo-status-bar";
import { PlayerScreen } from "./src/screens/PlayerScreen";

export default function App() {
  return (
    <>
      <StatusBar style="light" hidden />
      <PlayerScreen />
    </>
  );
}
```

Create `apps/player-demo/src/screens/PlayerScreen.tsx` with:

```tsx
import { StyleSheet, Text, View } from "react-native";

export function PlayerScreen() {
  return (
    <View style={styles.root}>
      <Text style={styles.title}>DramePulse Player Demo</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#080808"
  },
  title: {
    color: "#fff",
    fontSize: 20,
    fontWeight: "700"
  }
});
```

- [ ] **Step 4: Update ignore rules for Expo local output**

Add these lines under the Node/frontend section of `.gitignore`:

```gitignore
.expo/
web-build/
```

- [ ] **Step 5: Install dependencies**

Run:

```bash
cd apps/player-demo
npm install
```

Expected: `package-lock.json` is created and dependencies install successfully.

- [ ] **Step 6: Verify scaffold**

Run:

```bash
cd apps/player-demo
npm run typecheck
```

Expected: TypeScript completes with exit code 0.

### Task 2: Add Fixtures and Domain Logic

**Files:**
- Create: `apps/player-demo/src/fixtures/danmaku.json`
- Create: `apps/player-demo/src/fixtures/interaction-plan-generation.json`
- Create: `apps/player-demo/src/domain/types.ts`
- Create: `apps/player-demo/src/domain/fixtures.ts`
- Create: `apps/player-demo/src/domain/events.ts`
- Create: `apps/player-demo/src/domain/__tests__/events.test.ts`
- Create: `apps/player-demo/src/domain/__tests__/fixtures.test.ts`

- [ ] **Step 1: Copy local fixtures**

Copy:

```bash
cp data/case1/ep01.json apps/player-demo/src/fixtures/danmaku.json
cp example_output/case1_ep01/interaction_plan_generation.json apps/player-demo/src/fixtures/interaction-plan-generation.json
```

Expected: both JSON files exist under `apps/player-demo/src/fixtures/`.

- [ ] **Step 2: Define domain types**

Create `apps/player-demo/src/domain/types.ts` with interfaces for `DanmakuItem`, `InteractionOption`, `InteractionPlan`, `UserEvent`, `InteractionStats`, and `PlayerFixtures`.

- [ ] **Step 3: Write fixture adapter tests**

Create `apps/player-demo/src/domain/__tests__/fixtures.test.ts` covering:

```ts
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
```

- [ ] **Step 4: Run fixture test and verify red**

Run:

```bash
cd apps/player-demo
npm test -- src/domain/__tests__/fixtures.test.ts
```

Expected: FAIL because `../fixtures` does not exist yet.

- [ ] **Step 5: Implement fixture adapter**

Create `apps/player-demo/src/domain/fixtures.ts` to import the two JSON files, normalize `danmaku` and `interaction_plans`, filter to active `danmaku_poll`, and sort by `trigger_time`.

- [ ] **Step 6: Write event reducer tests**

Create `apps/player-demo/src/domain/__tests__/events.test.ts` covering:

```ts
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
  feedback: { type: "poll_result", show_ratio: true, show_resonance_text: true, resonance_text_template: "你和 {ratio}% 的观众一样选择了「{option}」" },
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
    let stats = updateStats(undefined, createUserEvent({ eventType: "interaction_exposure", plan, clientTime: 9, nowSeconds: 1 }));
    stats = updateStats(stats, createUserEvent({ eventType: "option_click", plan, optionId: "o_1", clientTime: 9.2, nowSeconds: 2 }));
    stats = updateStats(stats, createUserEvent({ eventType: "feedback_shown", plan, optionId: "o_1", clientTime: 9.5, nowSeconds: 3 }));
    stats = updateStats(stats, createUserEvent({ eventType: "interaction_dismiss", plan, clientTime: 12.1, nowSeconds: 4 }));

    expect(stats.exposure_count).toBe(1);
    expect(stats.click_count).toBe(1);
    expect(stats.feedback_shown_count).toBe(1);
    expect(stats.dismiss_count).toBe(1);
    expect(stats.option_click_count.o_1).toBe(1);
    expect(stats.option_click_rate.o_1).toBe(1);
  });
});
```

- [ ] **Step 7: Run event tests and verify red**

Run:

```bash
cd apps/player-demo
npm test -- src/domain/__tests__/events.test.ts
```

Expected: FAIL because `../events` does not exist yet.

- [ ] **Step 8: Implement event helpers**

Create `apps/player-demo/src/domain/events.ts` with:

- `createUserEvent(...)`;
- `createInitialStats()`;
- `updateStats(stats, event)`;
- deterministic `option_click_rate` based on option clicks divided by total clicks.

- [ ] **Step 9: Verify domain tests**

Run:

```bash
cd apps/player-demo
npm test -- src/domain
npm run typecheck
```

Expected: tests and typecheck pass.

### Task 3: Build Player UI and Interaction Loop

**Files:**
- Modify: `apps/player-demo/src/screens/PlayerScreen.tsx`
- Create: `apps/player-demo/src/components/VideoStage.tsx`
- Create: `apps/player-demo/src/components/DanmakuLayer.tsx`
- Create: `apps/player-demo/src/components/InteractionPollBar.tsx`
- Create: `apps/player-demo/src/components/FeedbackBurst.tsx`
- Create: `apps/player-demo/src/components/PlayerChrome.tsx`
- Create: `apps/player-demo/src/components/DebugPanel.tsx`
- Create: `apps/player-demo/src/theme.ts`

- [ ] **Step 1: Copy video asset for Expo bundling**

Run:

```bash
mkdir -p apps/player-demo/assets/video
cp data/case1/ep01.mp4 apps/player-demo/assets/video/ep01.mp4
```

Expected: `apps/player-demo/assets/video/ep01.mp4` exists.

- [ ] **Step 2: Build theme constants**

Create `apps/player-demo/src/theme.ts` with dark overlay colors, red-orange accent, spacing, and text sizes.

- [ ] **Step 3: Implement `VideoStage`**

Use `expo-video`'s `useVideoPlayer` and `VideoView` to play `../../assets/video/ep01.mp4`, loop disabled, native controls disabled, and call `onTimeChange(currentTime)` on interval updates.

- [ ] **Step 4: Implement `PlayerChrome`**

Render top controls, right-side action rail, bottom metadata, and bottom tab labels using React Native views and icons.

- [ ] **Step 5: Implement `DanmakuLayer`**

Render currently relevant danmaku items based on `currentTime`, each as moving or staged text rows. Use deterministic lanes so the layer is stable across renders.

- [ ] **Step 6: Implement `InteractionPollBar`**

Render question and 2-3 option pills. Default state uses dark translucent styling. Selected/result state uses red-orange accent and resonance text template.

- [ ] **Step 7: Implement `FeedbackBurst`**

When an option is selected, show 2-3 highlighted danmaku texts derived from selected option `danmaku_text` and nearby source danmaku.

- [ ] **Step 8: Implement `DebugPanel`**

Toggle from top-right icon. Show current time, active plan, triggered plan IDs, event list, and stats.

- [ ] **Step 9: Wire `PlayerScreen` state**

Load fixtures with `getDemoFixtures()`. Track current time, active plan, triggered IDs, selected option, local events, stats, feedback burst, and debug visibility. Emit `interaction_exposure`, `option_click`, `feedback_shown`, and `interaction_dismiss` events through domain helpers.

- [ ] **Step 10: Verify app typecheck**

Run:

```bash
cd apps/player-demo
npm run typecheck
npm test
```

Expected: both pass.

### Task 4: Run and Smoke Check

**Files:**
- Modify: `README.md`
- Modify: `docs/develop-docs/status/current-implementation.md`

- [ ] **Step 1: Update docs with run command**

Add an Expo player demo section to `README.md`:

```bash
cd apps/player-demo
npm install
npm start
```

Mention that iOS and Android can use Expo Go and that first-run video asset is bundled locally.

- [ ] **Step 2: Update current implementation status**

Add `apps/player-demo/` to `docs/develop-docs/status/current-implementation.md`, with the current limits: single page, local fixtures, local stats, no backend API.

- [ ] **Step 3: Run full verification**

Run:

```bash
python -m unittest discover -s tests
cd apps/player-demo
npm test
npm run typecheck
```

Expected: Python tests pass; Expo app tests pass; TypeScript passes.

- [ ] **Step 4: Start Expo server**

Run:

```bash
cd apps/player-demo
npm start
```

Expected: Expo server starts and prints a QR code / local URL for Expo Go.

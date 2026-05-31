# Player Storyboard Chapter Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lightweight story chapter timeline support to the mobile player: chapter ticks in the progress bar and storyboard preview/title while dragging.

**Architecture:** Keep the main interaction inside the existing `PlayerControls` because it already owns drag state and seek commit. Add pure domain helpers for chapter lookup and storyboard sprite-sheet cell lookup so behavior can be tested without React Native rendering. Add an offline Python storyboard generator that creates sprite sheets plus a manifest for future static hosting.

**Tech Stack:** Python `pytest`, OpenCV/ffmpeg helpers already used by `pipelines.utils`, React Native + Expo, Jest, TypeScript.

---

### Task 1: Storyboard Generator

**Files:**
- Create: `scripts/generate_storyboard.py`
- Test: `tests/test_generate_storyboard.py`

- [x] Write tests for sprite sheet manifest generation with fake frame images.
- [x] Run `PYTHONPATH=. pytest tests/test_generate_storyboard.py -q` and verify it fails because the script does not exist.
- [x] Implement `build_storyboard_from_frames()` and CLI plumbing.
- [x] Run `PYTHONPATH=. pytest tests/test_generate_storyboard.py -q` and verify it passes.

### Task 2: Frontend Domain Helpers

**Files:**
- Create: `apps/player-demo/src/domain/storyNavigation.ts`
- Test: `apps/player-demo/src/domain/__tests__/storyNavigation.test.ts`

- [x] Write Jest tests for chapter lookup, tick percentage calculation, and storyboard cell lookup.
- [x] Run `npm test -- storyNavigation.test.ts` in `apps/player-demo` and verify it fails because helpers do not exist.
- [x] Implement helper types and pure functions.
- [x] Run `npm test -- storyNavigation.test.ts` and verify it passes.

### Task 3: Player API Data Fields

**Files:**
- Modify: `apps/player-demo/src/domain/playerApi.ts`
- Modify tests: `apps/player-demo/src/domain/__tests__/playerApi.test.ts`

- [x] Extend player API tests to normalize optional `story_chapters` and `storyboard`.
- [x] Run `npm test -- playerApi.test.ts` and verify it fails.
- [x] Add optional `storyChapters` and `storyboard` fields to `PlayerVideo`.
- [x] Run `npm test -- playerApi.test.ts` and verify it passes.

### Task 4: Player Controls UI

**Files:**
- Modify: `apps/player-demo/src/components/PlayerControls.tsx`
- Modify: `apps/player-demo/src/components/PlayerPage.tsx`

- [x] Add props and rendering for chapter ticks and drag preview overlay.
- [x] Use domain helpers for tick and current chapter lookup.
- [x] Use storyboard manifest to render a cropped sprite sheet preview.
- [x] Keep fallback behavior identical when no story data exists.

### Task 5: Backend Story Asset Wiring

**Files:**
- Modify: `services/api/repositories/videos.py`
- Modify: `services/api/schemas.py`
- Modify: `services/api/main.py`
- Test: `tests/test_video_repository_story_assets.py`

- [x] Read optional `story_chapters.json` and `storyboard_manifest.json` by `video_id`.
- [x] Expose optional fields through `VideoResponse`.
- [x] Serve generated storyboard sheets from `/storyboards`.
- [x] Test local story asset loading and static sheet serving.

### Task 6: Verification

**Files:**
- No new files expected.

- [x] Run `PYTHONPATH=. pytest tests/test_generate_storyboard.py tests/test_video_repository_story_assets.py tests/test_api_routes.py tests/test_video_repository_cdn.py tests/test_story_chapter_generation.py tests/test_story_chapter_generation_script.py tests/test_story_chapter_generation_batch_script.py tests/test_story_chapter_generation_multimodal.py tests/test_story_chapter_generation_multimodal_script.py tests/test_story_chapter_generation_multimodal_batch_script.py -q`.
- [x] Run `npm run typecheck` in `apps/player-demo`.
- [x] Run `npm test` in `apps/player-demo`.
- [x] Check `git status --short` and summarize remaining untracked screenshots separately.

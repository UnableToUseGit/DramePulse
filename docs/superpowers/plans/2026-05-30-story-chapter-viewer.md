# Story Chapter Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local read-only web viewer for inspecting video scene cuts and generated story chapters.

**Architecture:** Add a small Python HTTP server under `scripts/` that indexes the external validation dataset and serves a static HTML/CSS/JS viewer from `apps/story-chapter-viewer/`. The frontend calls JSON APIs, plays local video through the server, renders scene ticks and chapter bands, and supports click-to-seek.

**Tech Stack:** Python standard library HTTP server, JSON fixtures, static HTML/CSS/JavaScript, pytest.

---

### Task 1: Dataset Indexing And API Data

**Files:**
- Create: `scripts/story_chapter_viewer_server.py`
- Test: `tests/test_story_chapter_viewer_server.py`

- [ ] Write tests for discovering episodes and assembling episode detail from a temporary dataset.
- [ ] Implement pure helper functions: `discover_episodes(dataset_root, chapter_output_root=None)`, `load_episode_detail(index_entry)`, and `make_episode_id(series_slug, episode_slug)`.
- [ ] Run `PYTHONPATH=. pytest tests/test_story_chapter_viewer_server.py -q`.

### Task 2: Static Viewer UI

**Files:**
- Create: `apps/story-chapter-viewer/index.html`
- Create: `apps/story-chapter-viewer/styles.css`
- Create: `apps/story-chapter-viewer/app.js`

- [ ] Build a three-column desktop tool: episode rail, video/timeline workspace, chapter inspector.
- [ ] Fetch `/api/episodes`, load the first episode, then fetch `/api/episodes/{episode_id}`.
- [ ] Render scene ticks, chapter bands, chapter list, current playback time, and active chapter state.
- [ ] Implement click-to-seek for chapter bands and chapter list rows.

### Task 3: HTTP Server Wiring

**Files:**
- Modify: `scripts/story_chapter_viewer_server.py`

- [ ] Serve static files from `apps/story-chapter-viewer`.
- [ ] Serve `GET /api/episodes`, `GET /api/episodes/{episode_id}`, and `GET /media/{episode_id}/video.mp4`.
- [ ] Add CLI args: `--dataset-root`, `--chapter-output-root`, `--host`, `--port`.

### Task 4: Verification

**Commands:**
- `PYTHONPATH=. pytest tests/test_story_chapter_viewer_server.py -q`
- `python scripts/story_chapter_viewer_server.py --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm --port 8765`

- [ ] Run the unit tests.
- [ ] Start the local server and confirm it prints the viewer URL.
- [ ] Use a browser smoke check if available, otherwise verify API responses with `curl`.

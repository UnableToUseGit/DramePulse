# Douyin CSV Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CSV-driven Douyin metadata and danmaku collection under `scripts/`, writing each result into the normalized external `VideoData/raw/<series_id>/epXX/douyin.json` directory.

**Architecture:** Keep the existing Playwright collection pipeline unchanged. Add a small CSV manifest adapter that produces the same episode dictionaries used by the existing collector, plus an output path resolver that switches between legacy flat JSON output and dataset-aligned `douyin.json` output.

**Tech Stack:** Python standard library (`argparse`, `csv`, `json`, `pathlib`, `re`), pytest for unit tests, existing Playwright runtime for real collection.

---

### Task 1: CSV Manifest Parsing

**Files:**
- Modify: `scripts/douyin_danmaku_collector.py`
- Create: `tests/test_douyin_danmaku_collector.py`

- [ ] **Step 1: Write failing tests**

Add tests for header CSV, headerless CSV, episode normalization, unknown series errors, and dataset output path resolution.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_douyin_danmaku_collector.py -q
```

Expected: fails because CSV helpers do not exist yet.

- [ ] **Step 3: Implement CSV helpers**

Add:

- `SERIES_SLUGS`
- `normalize_episode_no`
- `load_csv_manifest`
- `episode_output_path`

The helpers should return the same core keys as legacy `load_manifest`: `episode_id`, `video_id`, and `video_url`, plus `series_name`, `series_id`, `episode_no`, and `episode_label`.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_douyin_danmaku_collector.py -q
```

Expected: all tests in this file pass.

### Task 2: CLI Wiring

**Files:**
- Modify: `scripts/douyin_danmaku_collector.py`
- Modify: `tests/test_douyin_danmaku_collector.py`

- [ ] **Step 1: Write failing tests**

Add parser/run-selection tests that prove `--csv` uses `--output-dir` and legacy mode still uses `--manifest` with `--out-dir`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_douyin_danmaku_collector.py -q
```

Expected: fails because parser and `run_collection` do not support `--csv` yet.

- [ ] **Step 3: Implement CLI wiring**

Add `--csv` and `--output-dir`. In `run_collection`, load CSV episodes when `args.csv` is set, create the root output directory, and call `episode_output_path` for each episode. Keep old behavior when `args.csv` is not set.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_douyin_danmaku_collector.py -q
```

Expected: all focused tests pass.

### Task 3: Final Verification

**Files:**
- Modify: `scripts/douyin_danmaku_collector.py`
- Create: `scripts/douyin_targets.csv`
- Test: `tests/test_douyin_danmaku_collector.py`

- [ ] **Step 1: Run syntax check**

Run:

```bash
python -m py_compile scripts/douyin_danmaku_collector.py
```

Expected: exits 0.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python -m pytest tests/test_douyin_danmaku_collector.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Inspect git diff**

Run:

```bash
git diff -- scripts/douyin_danmaku_collector.py scripts/douyin_targets.csv tests/test_douyin_danmaku_collector.py docs/superpowers/specs/2026-05-24-douyin-csv-collector-design.md docs/superpowers/plans/2026-05-24-douyin-csv-collector.md
```

Expected: diff contains only the CSV collector design, tests, and script changes.

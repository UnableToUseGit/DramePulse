# Video Manifest Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `video_manifest.json` from `VideoData/raw` and import it into the backend `videos` table with series and Douyin fields.

**Architecture:** Add a repository-local manifest generator under `scripts/` that reads `video.mp4` and `douyin.json` from a supplied `--data-root`. Add an API-side importer under `services/api/scripts/` that creates or migrates the `videos` table and upserts manifest rows. Extend API video responses so the frontend can render series metadata and access danmaku through a future endpoint.

**Tech Stack:** Python standard library, SQLite/MySQL-compatible SQL paths already used by `services.api.db`, pytest/unittest.

---

### Task 1: Manifest Generation

**Files:**
- Create: `scripts/generate_video_manifest.py`
- Create: `tests/test_generate_video_manifest.py`

- [ ] **Step 1: Write failing tests**

Add tests that build a temporary `raw/<series_id>/epXX/` tree with `video.mp4` and `douyin.json`, then assert generated manifest fields match `docs/develop-docs/video-manifest-design.md`.

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_generate_video_manifest.py -q
```

Expected: fails because `scripts.generate_video_manifest` does not exist.

- [ ] **Step 3: Implement generator**

Implement functions:

- `build_video_entry(data_root: Path, episode_dir: Path) -> dict`
- `generate_manifest(data_root: Path) -> dict`
- `write_manifest(data_root: Path, output: Path | None = None) -> Path`
- `main(argv: Sequence[str] | None = None) -> int`

Use `scripts.douyin_danmaku_collector.SERIES_SLUGS` inverted to map `series_id` to `series_name`.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_generate_video_manifest.py -q
```

Expected: all tests pass.

### Task 2: videos Table Migration and Manifest Import

**Files:**
- Modify: `services/api/scripts/init_local_dev.py`
- Modify: `services/api/scripts/init_db.py`
- Create: `services/api/scripts/import_video_manifest.py`
- Create: `tests/test_import_video_manifest.py`

- [ ] **Step 1: Write failing tests**

Add SQLite tests proving:

- `ensure_video_schema()` creates/migrates new columns.
- `import_video_manifest()` upserts manifest rows.
- imported `douyin_json_path`, `series_name`, and `episode_label` are stored.

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_import_video_manifest.py -q
```

Expected: fails because importer does not exist.

- [ ] **Step 3: Implement migration and importer**

Implement:

- `ensure_video_schema(settings=None)`
- `load_manifest(path: Path) -> dict`
- `import_video_manifest(manifest_path: Path, data_root: Path | None = None) -> int`
- CLI parser with `--manifest` and `--data-root`

Keep SQLite and MySQL branches compatible with existing `db_cursor()` and `sql_placeholder()`.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_import_video_manifest.py -q
```

Expected: all tests pass.

### Task 3: API Video Response Fields

**Files:**
- Modify: `services/api/schemas.py`
- Modify: `services/api/repositories/videos.py`
- Modify: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing tests**

Update API route tests so `/api/videos` returns:

- `series_id`
- `series_name`
- `episode_label`
- `douyin_video_id`
- `danmaku_url`

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_api_routes.py -q
```

Expected: fails because response schema/repository do not include new fields.

- [ ] **Step 3: Implement response extension**

Extend `VideoResponse` and `_to_video_response()`. Add `danmaku_url` as `/api/videos/{video_id}/danmaku`; the actual danmaku endpoint is a later task.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_api_routes.py -q
```

Expected: API route tests pass.

### Task 4: Final Verification

**Files:**
- All changed files from Tasks 1-3.

- [ ] **Step 1: Syntax check**

Run:

```bash
python -m py_compile scripts/generate_video_manifest.py services/api/scripts/import_video_manifest.py services/api/scripts/init_local_dev.py services/api/scripts/init_db.py services/api/repositories/videos.py services/api/schemas.py
```

Expected: exits 0.

- [ ] **Step 2: Focused tests**

Run:

```bash
python -m pytest tests/test_generate_video_manifest.py tests/test_import_video_manifest.py tests/test_api_routes.py -q
```

Expected: all focused tests pass.

- [ ] **Step 3: Existing collector tests**

Run:

```bash
python -m pytest tests/test_douyin_danmaku_collector.py -q
```

Expected: collector tests still pass.

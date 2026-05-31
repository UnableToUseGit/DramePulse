# Story Chapter Multimodal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent high-cost multimodal story chapter generation pipeline that uses one video frame per second plus subtitles.

**Architecture:** Add a new pipeline module that reuses transcription parsing from the text-only pipeline and frame extraction from `pipelines.utils`. Add single-episode and batch CLIs that mirror the existing story chapter scripts but write to a multimodal output root.

**Tech Stack:** Python, OpenCV/ffmpeg frame extraction through existing utilities, Volc Ark multimodal client, pytest.

---

### Task 1: Pipeline Core

**Files:**
- Create: `pipelines/story_chapter_generation_multimodal.py`
- Create: `tests/test_story_chapter_generation_multimodal.py`

- [ ] Add tests for one-frame-per-second timestamp generation.
- [ ] Add tests for prompt sections and frame timestamp boundary rules.
- [ ] Add tests that the pipeline passes `image_paths` and `frame_timestamps_seconds` to the LLM client.
- [ ] Implement the multimodal pipeline with raw LLM chapter parsing reused from `story_chapter_generation`.

### Task 2: Single-Episode CLI

**Files:**
- Create: `scripts/run_story_chapter_generation_multimodal.py`
- Create: `tests/test_story_chapter_generation_multimodal_script.py`

- [ ] Add tests that CLI passes `video_path`, `video_metadata`, `transcription_path`, and `output_root`.
- [ ] Implement CLI with `--video`, `--transcription`, `--scene-detection`, `--output-root`, and `--env-file`.

### Task 3: Batch CLI

**Files:**
- Create: `scripts/run_story_chapter_generation_multimodal_batch.py`
- Create: `tests/test_story_chapter_generation_multimodal_batch_script.py`

- [ ] Add tests for discovering validation dataset episodes with `video.mp4`.
- [ ] Add tests for `--only-missing` and summary writing.
- [ ] Implement batch runner writing to `output/story_chapter_multimodal_validation`.

### Task 4: Verification

**Commands:**
- `PYTHONPATH=. pytest tests/test_story_chapter_generation_multimodal.py tests/test_story_chapter_generation_multimodal_script.py tests/test_story_chapter_generation_multimodal_batch_script.py -q`
- `PYTHONPATH=. pytest tests/test_story_chapter_generation.py tests/test_story_chapter_generation_script.py tests/test_story_chapter_generation_batch_script.py -q`

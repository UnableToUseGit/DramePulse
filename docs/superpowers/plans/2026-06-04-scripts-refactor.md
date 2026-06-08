# Scripts Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `scripts/` 从单层散乱脚本整理为按算法线和工具域分组的结构，同时保留当前顶层命令兼容。

**Architecture:** 新增 `scripts/algorithm/` 作为三条确定算法线的入口目录，新增 `scripts/algorithm/common.py` 承载数据集发现、写出、失败诊断等 batch 公共逻辑。顶层旧脚本保留为 shim，先不删除，确保 README 命令和本地习惯命令继续可运行。

**Tech Stack:** Python stdlib `argparse` / `pathlib` / `json`，现有 `pipelines.client.factory`，现有 pytest 测试体系。

---

## 目标结构

```text
scripts/
  algorithm/
    __init__.py
    common.py
    expression_trigger/
      __init__.py
      run_workflow_batch.py
      run_mllm_baseline_batch.py
      run_text_baseline_batch.py
    story_chapter/
      __init__.py
      run_text.py
      run_text_batch.py
      run_mllm.py
      run_mllm_batch.py
    inner_voice_danmaku/
      __init__.py
      run.py
  tools/
    __init__.py
    annotation/
      __init__.py
      serve_annotation_tool.py
      serve_algorithm_review_tool.py
      story_chapter_viewer_server.py
    media/
      __init__.py
      generate_audio_visualization.py
      generate_video_manifest.py
      run_scene_detection.py
      transcribe_video.py
    data/
      __init__.py
      analyze_danmaku_expression_triggers.py
      analyze_subtitle_dialogue_density.py
      algorithm_danmaku_csv.py
      douyin_danmaku_collector.py
      evaluate_expression_trigger_annotations.py
  transcription/
    ...
```

顶层保留这些 shim：

```text
scripts/run_expression_trigger_workflow_batch.py
scripts/run_expression_trigger_mllm_baseline_batch.py
scripts/run_expression_trigger_text_baseline_batch.py
scripts/run_workflow_expression_trigger_detection_batch.py
scripts/run_expression_trigger_detection_batch.py
scripts/run_text_expression_trigger_detection_batch.py
scripts/run_story_chapter_generation.py
scripts/run_story_chapter_generation_batch.py
scripts/run_story_chapter_generation_multimodal.py
scripts/run_story_chapter_generation_multimodal_batch.py
scripts/run_inner_voice_danmaku_generation.py
```

## Task 1: 新建脚本包骨架和直接执行约束

**Files:**
- Create: `scripts/algorithm/__init__.py`
- Create: `scripts/algorithm/expression_trigger/__init__.py`
- Create: `scripts/algorithm/story_chapter/__init__.py`
- Create: `scripts/algorithm/inner_voice_danmaku/__init__.py`
- Create: `scripts/tools/__init__.py`
- Create: `scripts/tools/annotation/__init__.py`
- Create: `scripts/tools/media/__init__.py`
- Create: `scripts/tools/data/__init__.py`
- Modify: `tests/test_expression_trigger_detection_batch_script.py`
- Modify: `tests/test_workflow_expression_trigger_detection_batch_script.py`
- Modify: `tests/test_text_expression_trigger_detection_batch_script.py`
- Modify: `tests/test_story_chapter_generation_batch_script.py`
- Modify: `tests/test_story_chapter_generation_multimodal_batch_script.py`
- Modify: `tests/test_inner_voice_danmaku_generation.py`

- [ ] **Step 1: Write failing direct-execution tests for new paths**

Add subprocess checks like:

```python
def test_new_workflow_algorithm_script_runs_when_executed_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/algorithm/expression_trigger/run_workflow_batch.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "workflow Expression Trigger Detection" in result.stdout
```

Add equivalent tests for:

```text
scripts/algorithm/expression_trigger/run_mllm_baseline_batch.py
scripts/algorithm/expression_trigger/run_text_baseline_batch.py
scripts/algorithm/story_chapter/run_text.py
scripts/algorithm/story_chapter/run_text_batch.py
scripts/algorithm/story_chapter/run_mllm.py
scripts/algorithm/story_chapter/run_mllm_batch.py
scripts/algorithm/inner_voice_danmaku/run.py
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest \
  tests/test_expression_trigger_detection_batch_script.py \
  tests/test_workflow_expression_trigger_detection_batch_script.py \
  tests/test_text_expression_trigger_detection_batch_script.py \
  tests/test_story_chapter_generation_batch_script.py \
  tests/test_story_chapter_generation_multimodal_batch_script.py \
  tests/test_inner_voice_danmaku_generation.py \
  -q
```

Expected: FAIL because new script paths do not exist.

- [ ] **Step 3: Create package skeleton and minimal wrappers**

Each new wrapper should start with:

```python
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
```

For example `scripts/algorithm/expression_trigger/run_workflow_batch.py`:

```python
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_workflow_expression_trigger_detection_batch import (
    DEFAULT_OUTPUT_ROOT,
    build_parser,
    build_pipeline,
    main,
    print_workflow_progress,
    write_workflow_episode_output,
)

__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "build_parser",
    "build_pipeline",
    "main",
    "print_workflow_progress",
    "write_workflow_episode_output",
]


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python -m pytest \
  tests/test_expression_trigger_detection_batch_script.py \
  tests/test_workflow_expression_trigger_detection_batch_script.py \
  tests/test_text_expression_trigger_detection_batch_script.py \
  tests/test_story_chapter_generation_batch_script.py \
  tests/test_story_chapter_generation_multimodal_batch_script.py \
  tests/test_inner_voice_danmaku_generation.py \
  -q
```

Commit:

```bash
git add scripts/algorithm scripts/tools tests
git commit -m "refactor: add structured script entrypoints"
```

## Task 2: 抽出算法 batch 公共能力

**Files:**
- Create: `scripts/algorithm/common.py`
- Modify: `scripts/run_expression_trigger_detection_batch.py`
- Modify: `scripts/run_workflow_expression_trigger_detection_batch.py`
- Modify: `scripts/run_text_expression_trigger_detection_batch.py`
- Modify: `scripts/run_inner_voice_danmaku_generation.py`
- Test: existing batch script tests

- [ ] **Step 1: Write import tests for common utilities**

Add to `tests/test_expression_trigger_detection_batch_script.py`:

```python
def test_algorithm_common_exports_dataset_and_output_helpers() -> None:
    from scripts.algorithm.common import (
        DEFAULT_DATA_ROOT,
        EpisodeInput,
        discover_episodes,
        extract_video_metadata,
        load_source_payload,
        now_iso,
        write_failure_diagnostics,
    )

    assert DEFAULT_DATA_ROOT.name == "DataForAlgorithm"
    assert EpisodeInput.__name__ == "EpisodeInput"
    assert callable(discover_episodes)
    assert callable(extract_video_metadata)
    assert callable(load_source_payload)
    assert callable(now_iso)
    assert callable(write_failure_diagnostics)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest tests/test_expression_trigger_detection_batch_script.py::test_algorithm_common_exports_dataset_and_output_helpers -q
```

Expected: FAIL because `scripts.algorithm.common` does not exist or lacks exports.

- [ ] **Step 3: Move shared definitions into `scripts/algorithm/common.py`**

Move these from `scripts/run_expression_trigger_detection_batch.py`:

```text
DEFAULT_DATA_ROOT
EpisodeInput
discover_episodes
load_source_payload
extract_video_metadata
extract_danmaku_items
now_iso
write_failure_diagnostics
```

Keep `build_llm_client` and `build_ark_client` imported from `pipelines.client.factory`; do not duplicate client construction.

- [ ] **Step 4: Turn old locations into imports**

In `scripts/run_expression_trigger_detection_batch.py`, import moved names:

```python
from scripts.algorithm.common import (
    DEFAULT_DATA_ROOT,
    EpisodeInput,
    discover_episodes,
    extract_danmaku_items,
    extract_video_metadata,
    load_source_payload,
    now_iso,
    write_failure_diagnostics,
)
```

Apply the same import direction to workflow, text baseline, and inner voice scripts.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python -m pytest \
  tests/test_expression_trigger_detection_batch_script.py \
  tests/test_workflow_expression_trigger_detection_batch_script.py \
  tests/test_text_expression_trigger_detection_batch_script.py \
  tests/test_inner_voice_danmaku_generation.py \
  -q
```

Commit:

```bash
git add scripts/algorithm/common.py scripts/run_expression_trigger_detection_batch.py scripts/run_workflow_expression_trigger_detection_batch.py scripts/run_text_expression_trigger_detection_batch.py scripts/run_inner_voice_danmaku_generation.py tests
git commit -m "refactor: extract algorithm script common utilities"
```

## Task 3: 迁移 Expression Trigger 脚本真实实现

**Files:**
- Modify: `scripts/algorithm/expression_trigger/run_mllm_baseline_batch.py`
- Modify: `scripts/algorithm/expression_trigger/run_workflow_batch.py`
- Modify: `scripts/algorithm/expression_trigger/run_text_baseline_batch.py`
- Modify: top-level expression trigger scripts as shims
- Test: expression trigger batch tests

- [ ] **Step 1: Add module ownership assertions**

Add tests asserting new modules own public `main`:

```python
def test_expression_trigger_workflow_main_lives_in_algorithm_package() -> None:
    from scripts.algorithm.expression_trigger.run_workflow_batch import main

    assert main.__module__ == "scripts.algorithm.expression_trigger.run_workflow_batch"
```

Add equivalent assertions for MLLM and text baseline.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest \
  tests/test_expression_trigger_detection_batch_script.py \
  tests/test_workflow_expression_trigger_detection_batch_script.py \
  tests/test_text_expression_trigger_detection_batch_script.py \
  -q
```

Expected: FAIL because new modules still re-export old `main`.

- [ ] **Step 3: Move real implementation into new modules**

Move implementation code:

```text
scripts/run_expression_trigger_detection_batch.py
  -> scripts/algorithm/expression_trigger/run_mllm_baseline_batch.py

scripts/run_workflow_expression_trigger_detection_batch.py
  -> scripts/algorithm/expression_trigger/run_workflow_batch.py

scripts/run_text_expression_trigger_detection_batch.py
  -> scripts/algorithm/expression_trigger/run_text_baseline_batch.py
```

Top-level files become shim-only:

```python
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.algorithm.expression_trigger.run_workflow_batch import *  # noqa: F403
from scripts.algorithm.expression_trigger.run_workflow_batch import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run direct command smoke checks**

Run:

```bash
python scripts/run_expression_trigger_workflow_batch.py --help
python scripts/algorithm/expression_trigger/run_workflow_batch.py --help
python scripts/run_expression_trigger_mllm_baseline_batch.py --help
python scripts/algorithm/expression_trigger/run_mllm_baseline_batch.py --help
python scripts/run_expression_trigger_text_baseline_batch.py --help
python scripts/algorithm/expression_trigger/run_text_baseline_batch.py --help
```

Expected: all exit 0.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python -m pytest \
  tests/test_expression_trigger_detection.py \
  tests/test_text_expression_trigger_detection.py \
  tests/test_workflow_expression_trigger_detection.py \
  tests/test_expression_trigger_detection_batch_script.py \
  tests/test_workflow_expression_trigger_detection_batch_script.py \
  tests/test_text_expression_trigger_detection_batch_script.py \
  -q
```

Commit:

```bash
git add scripts/algorithm/expression_trigger scripts/run_expression_trigger_detection_batch.py scripts/run_workflow_expression_trigger_detection_batch.py scripts/run_text_expression_trigger_detection_batch.py scripts/run_expression_trigger_workflow_batch.py scripts/run_expression_trigger_mllm_baseline_batch.py scripts/run_expression_trigger_text_baseline_batch.py tests
git commit -m "refactor: move expression trigger scripts into algorithm package"
```

## Task 4: 迁移 Story Chapter 和 Inner Voice 脚本

**Files:**
- Modify: `scripts/algorithm/story_chapter/run_text.py`
- Modify: `scripts/algorithm/story_chapter/run_text_batch.py`
- Modify: `scripts/algorithm/story_chapter/run_mllm.py`
- Modify: `scripts/algorithm/story_chapter/run_mllm_batch.py`
- Modify: `scripts/algorithm/inner_voice_danmaku/run.py`
- Modify: related top-level shims
- Test: story chapter and inner voice tests

- [ ] **Step 1: Add module ownership assertions**

Add assertions like:

```python
def test_story_chapter_text_batch_main_lives_in_algorithm_package() -> None:
    from scripts.algorithm.story_chapter.run_text_batch import main

    assert main.__module__ == "scripts.algorithm.story_chapter.run_text_batch"
```

Add equivalent assertions for:

```text
scripts.algorithm.story_chapter.run_text
scripts.algorithm.story_chapter.run_mllm
scripts.algorithm.story_chapter.run_mllm_batch
scripts.algorithm.inner_voice_danmaku.run
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest \
  tests/test_story_chapter_generation.py \
  tests/test_story_chapter_generation_batch_script.py \
  tests/test_story_chapter_generation_multimodal.py \
  tests/test_story_chapter_generation_multimodal_batch_script.py \
  tests/test_inner_voice_danmaku_generation.py \
  -q
```

Expected: FAIL because new modules still re-export old `main`.

- [ ] **Step 3: Move real implementation into new modules**

Move:

```text
scripts/run_story_chapter_generation.py
  -> scripts/algorithm/story_chapter/run_text.py

scripts/run_story_chapter_generation_batch.py
  -> scripts/algorithm/story_chapter/run_text_batch.py

scripts/run_story_chapter_generation_multimodal.py
  -> scripts/algorithm/story_chapter/run_mllm.py

scripts/run_story_chapter_generation_multimodal_batch.py
  -> scripts/algorithm/story_chapter/run_mllm_batch.py

scripts/run_inner_voice_danmaku_generation.py
  -> scripts/algorithm/inner_voice_danmaku/run.py
```

Top-level scripts remain shim-only.

- [ ] **Step 4: Run direct command smoke checks**

Run:

```bash
python scripts/run_story_chapter_generation.py --help
python scripts/algorithm/story_chapter/run_text.py --help
python scripts/run_story_chapter_generation_batch.py --help
python scripts/algorithm/story_chapter/run_text_batch.py --help
python scripts/run_story_chapter_generation_multimodal.py --help
python scripts/algorithm/story_chapter/run_mllm.py --help
python scripts/run_story_chapter_generation_multimodal_batch.py --help
python scripts/algorithm/story_chapter/run_mllm_batch.py --help
python scripts/run_inner_voice_danmaku_generation.py --help
python scripts/algorithm/inner_voice_danmaku/run.py --help
```

Expected: all exit 0.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python -m pytest \
  tests/test_story_chapter_generation.py \
  tests/test_story_chapter_generation_batch_script.py \
  tests/test_story_chapter_generation_multimodal.py \
  tests/test_story_chapter_generation_multimodal_batch_script.py \
  tests/test_inner_voice_danmaku_generation.py \
  -q
```

Commit:

```bash
git add scripts/algorithm/story_chapter scripts/algorithm/inner_voice_danmaku scripts/run_story_chapter_generation.py scripts/run_story_chapter_generation_batch.py scripts/run_story_chapter_generation_multimodal.py scripts/run_story_chapter_generation_multimodal_batch.py scripts/run_inner_voice_danmaku_generation.py tests
git commit -m "refactor: move story and inner voice scripts into algorithm package"
```

## Task 5: 迁移工具类脚本并更新文档

**Files:**
- Move or shim: annotation/media/data tool scripts
- Modify: `README.md`
- Modify: `docs/develop-docs/status/expression-trigger-validation-observations-2026-06-04.md`
- Test: tool script tests

- [ ] **Step 1: Add direct execution tests for tool paths**

Add subprocess `--help` tests for:

```text
scripts/tools/annotation/serve_annotation_tool.py
scripts/tools/annotation/serve_algorithm_review_tool.py
scripts/tools/annotation/story_chapter_viewer_server.py
scripts/tools/media/generate_audio_visualization.py
scripts/tools/media/generate_video_manifest.py
scripts/tools/media/run_scene_detection.py
scripts/tools/media/transcribe_video.py
scripts/tools/data/analyze_danmaku_expression_triggers.py
scripts/tools/data/analyze_subtitle_dialogue_density.py
scripts/tools/data/evaluate_expression_trigger_annotations.py
```

- [ ] **Step 2: Move tool scripts with top-level shims**

For each moved script, keep the top-level filename as a shim with repo root path injection and `main()` forwarding.

- [ ] **Step 3: Leave high-risk collector scripts in place**

Do not move these in this pass:

```text
scripts/douyin_danmaku_collector.py
scripts/algorithm_danmaku_csv.py
scripts/debug_openai_reasoning_call.py
```

Reason: they are operational/debug tools with likely ad hoc local usage. Move them only after the core algorithm scripts are stable.

- [ ] **Step 4: Update README command examples**

Replace old examples with preferred new paths while documenting old shims:

```bash
python scripts/algorithm/expression_trigger/run_workflow_batch.py --video-id case1_ep01 --force
python scripts/algorithm/expression_trigger/run_mllm_baseline_batch.py --video-id case1_ep01 --force
python scripts/algorithm/expression_trigger/run_text_baseline_batch.py --video-id case1_ep01 --force
python scripts/algorithm/story_chapter/run_text.py case1_ep01
python scripts/algorithm/story_chapter/run_mllm.py case1_ep01
python scripts/algorithm/inner_voice_danmaku/run.py --video-id case1_ep01 --force
```

- [ ] **Step 5: Run full verification and commit**

Run:

```bash
python -m pytest -q
```

If sandbox blocks local socket or Playwright cache access, rerun the same command with approved escalation.

Commit:

```bash
git add scripts README.md docs/develop-docs/status/expression-trigger-validation-observations-2026-06-04.md tests
git commit -m "refactor: organize utility scripts"
```

## Validation Checklist

- [ ] `python scripts/run_expression_trigger_workflow_batch.py --help` works.
- [ ] `python scripts/algorithm/expression_trigger/run_workflow_batch.py --help` works.
- [ ] Existing README command remains valid through shim.
- [ ] New README command uses structured path.
- [ ] No algorithm script imports from deprecated highlight or interaction plan modules.
- [ ] `python -m pytest -q` passes.

## Non-Goals

- Do not remove top-level shims in this refactor.
- Do not rename output JSON files.
- Do not change model prompts or algorithm behavior.
- Do not move `scripts/transcription/`; it is already a structured package.
- Do not move `douyin_danmaku_collector.py` until core algorithm scripts are stable.

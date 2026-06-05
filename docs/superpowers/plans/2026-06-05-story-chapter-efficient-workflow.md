# Story Chapter Efficient Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the efficient Story Chapter workflow that recalls cheap boundary candidates, scores topic shifts with text LLM, selects final chapters with candidate-local MLLM frames plus full subtitles, and writes compatible `story_chapters.json` artifacts.

**Architecture:** Add `pipelines/story_chapter/workflow.py` as the main implementation while preserving existing text and MLLM baselines. Add CLI wrappers under `scripts/run_story_chapter_workflow*.py` and `scripts/algorithm/story_chapter/run_workflow*.py`, following existing story chapter script patterns.

**Tech Stack:** Python 3, `unittest`/`pytest`, existing `VolcArkLlmClient`, existing frame extraction utilities, existing Aliyun transcription JSON parser.

---

## File Structure

- Create: `pipelines/story_chapter/workflow.py`
  - Candidate data classes.
  - Rule candidate recall.
  - Text LLM topic shift prompt/parse.
  - MLLM selector prompt/parse.
  - Postprocess validation and fallback.
  - `StoryChapterWorkflowPipeline`.
- Modify: `pipelines/story_chapter/__init__.py`
  - Export `StoryChapterWorkflowPipeline`.
- Create: `scripts/run_story_chapter_workflow.py`
  - Single-episode CLI.
- Create: `scripts/run_story_chapter_workflow_batch.py`
  - Dataset batch CLI.
- Create: `scripts/algorithm/story_chapter/run_workflow.py`
  - Algorithm namespace wrapper.
- Create: `scripts/algorithm/story_chapter/run_workflow_batch.py`
  - Algorithm namespace batch wrapper.
- Create: `tests/test_story_chapter_workflow.py`
  - Unit tests for candidate recall, LLM parsing, selector postprocess, and full fake-client pipeline.
- Create: `tests/test_story_chapter_workflow_script.py`
  - CLI tests.
- Create: `tests/test_story_chapter_workflow_batch_script.py`
  - Batch discovery and summary tests.

## Task 1: Candidate Recall

**Files:**
- Create: `tests/test_story_chapter_workflow.py`
- Create: `pipelines/story_chapter/workflow.py`

- [ ] **Step 1: Write failing tests for rule recall**

Add tests that call `recall_boundary_candidates()` with utterances and scenes:

```python
def test_recall_boundary_candidates_uses_scene_pause_and_density_signals(self) -> None:
    utterances = [
        Utterance("u_001", 0.5, 2.0, "你到底是谁？"),
        Utterance("u_002", 2.2, 3.0, "我只是路过。"),
        Utterance("u_003", 5.2, 6.0, "合同已经签了。"),
        Utterance("u_004", 6.1, 6.8, "现在开始执行。"),
        Utterance("u_005", 7.0, 7.5, "走。"),
    ]
    scenes = [
        {"scene_id": "s_001", "start_time": 0.0, "end_time": 5.0},
        {"scene_id": "s_002", "start_time": 5.0, "end_time": 9.0},
    ]

    candidates = recall_boundary_candidates(
        utterances=utterances,
        scenes=scenes,
        video_duration_seconds=10.0,
        pause_threshold_seconds=1.2,
        density_window_seconds=3.0,
        merge_window_seconds=0.6,
    )

    merged = candidates[0]
    self.assertEqual(merged.time, 5.0)
    self.assertIn("scene_boundary", merged.signals)
    self.assertIn("long_pause", merged.signals)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_recall_boundary_candidates_uses_scene_pause_and_density_signals -q`

Expected: FAIL because `pipelines.story_chapter.workflow` does not exist.

- [ ] **Step 3: Implement candidate data classes and recall**

Create:

```python
@dataclass(frozen=True)
class BoundaryCandidate:
    candidate_id: str
    time: float
    rule_score: float
    score: float
    signals: list[str]
    evidence: dict[str, Any]
    topic_shift_score: float | None = None
    topic_shift_reason: str | None = None
```

Implement:

```python
def recall_boundary_candidates(
    *,
    utterances: Sequence[Utterance],
    scenes: Sequence[dict[str, Any]],
    video_duration_seconds: float,
    pause_threshold_seconds: float = 1.2,
    density_window_seconds: float = 12.0,
    merge_window_seconds: float = 3.0,
) -> list[BoundaryCandidate]:
    """Return merged, scored candidate chapter boundaries from cheap timeline signals."""
```

Scene candidates use scene start times except `0.0`. Long pause candidates use the next utterance start time, snapped to nearby scene boundary. Density candidates compare before/after character-per-second density. Merge candidates within `merge_window_seconds`, combine signals, keep nearest scene boundary time if present, and assign stable ids `bc_001`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_recall_boundary_candidates_uses_scene_pause_and_density_signals -q`

Expected: PASS.

## Task 2: Text LLM Topic Shift Scoring

**Files:**
- Modify: `tests/test_story_chapter_workflow.py`
- Modify: `pipelines/story_chapter/workflow.py`

- [ ] **Step 1: Write failing tests for prompt and parser**

Add fake text client and tests:

```python
def test_score_topic_shifts_updates_candidate_scores(self) -> None:
    client = FakeClient({"topic_shift_reviews": [{"candidate_id": "bc_001", "topic_shift_score": 0.9, "reason": "身份质疑转为身份揭露。"}]})
    candidate = BoundaryCandidate("bc_001", 5.0, 0.4, 0.4, ["scene_boundary"], {})

    scored = score_topic_shifts_with_llm(
        llm_client=client,
        video_id="demo_ep01",
        video_duration_seconds=10.0,
        utterances=[Utterance("u_001", 0.0, 1.0, "你是谁？"), Utterance("u_002", 5.0, 6.0, "我是继承人。")],
        candidates=[candidate],
    )

    self.assertEqual(scored[0].topic_shift_score, 0.9)
    self.assertGreater(scored[0].score, candidate.score)
    self.assertIn("bc_001", client.calls[0]["user_prompt"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_score_topic_shifts_updates_candidate_scores -q`

Expected: FAIL because scoring function is missing.

- [ ] **Step 3: Implement prompt, parser, and scoring**

Implement:

```python
def build_topic_shift_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    candidates: Sequence[BoundaryCandidate],
    context_utterance_count: int = 8,
) -> str:
    """Build a text-only JSON prompt for candidate-level topic shift scoring."""


def parse_topic_shift_reviews(raw: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return reviews keyed by candidate_id plus parse warnings."""


def score_topic_shifts_with_llm(
    *,
    llm_client: StoryChapterLlmClientProtocol,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    candidates: Sequence[BoundaryCandidate],
    context_utterance_count: int = 8,
    max_tokens: int = 2400,
) -> tuple[list[BoundaryCandidate], list[str], dict[str, Any]]:
    """Call text LLM once and return scored candidates, warnings, and raw response."""
```

Final score:

```text
score = 0.70 * rule_score + 0.30 * topic_shift_score
```

Clamp all scores to `0..1`. Unknown candidate ids are ignored with warnings.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_score_topic_shifts_updates_candidate_scores -q`

Expected: PASS.

## Task 3: MLLM Selector and Postprocess

**Files:**
- Modify: `tests/test_story_chapter_workflow.py`
- Modify: `pipelines/story_chapter/workflow.py`

- [ ] **Step 1: Write failing selector tests**

Add tests:

```python
def test_parse_selector_result_requires_candidate_boundaries_and_full_coverage(self) -> None:
    candidates = [BoundaryCandidate("bc_001", 5.0, 0.8, 0.8, ["scene_boundary"], {})]
    chapters, warnings = parse_and_validate_selector_result(
        raw={"chapters": [{"start_time": 0.0, "end_time": 5.0, "end_boundary_candidate_id": "bc_001", "title": "身份遭疑", "summary": "众人质疑身份。", "importance": 0.7}, {"start_time": 5.0, "end_time": 10.0, "end_boundary_candidate_id": None, "title": "身份揭露", "summary": "身份揭开。", "importance": 0.9}]},
        video_id="demo_ep01",
        video_duration_seconds=10.0,
        candidates=candidates,
    )

    self.assertEqual(warnings, [])
    self.assertEqual(chapters[0]["chapter_id"], "ch_demo_ep01_001")
    self.assertEqual(chapters[-1]["end_time"], 10.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_parse_selector_result_requires_candidate_boundaries_and_full_coverage -q`

Expected: FAIL because parser is missing.

- [ ] **Step 3: Implement selector prompts, parser, and fallback**

Implement:

```python
def build_selector_system_prompt() -> str:
    """Return the MLLM selector system prompt."""


def build_selector_user_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    utterances: Sequence[Utterance],
    candidates: Sequence[BoundaryCandidate],
    frame_timestamps_by_candidate: dict[str, list[float]],
    constraints: ChapterSelectionConstraints,
) -> str:
    """Build selector prompt with full subtitles and candidate-local frame metadata."""


def parse_and_validate_selector_result(
    *,
    raw: dict[str, Any],
    video_id: str,
    video_duration_seconds: float,
    candidates: Sequence[BoundaryCandidate],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse MLLM selector output and enforce chapter coverage constraints."""


def build_fallback_chapters(
    *,
    video_id: str,
    video_duration_seconds: float,
    candidates: Sequence[BoundaryCandidate],
    constraints: ChapterSelectionConstraints,
) -> list[dict[str, Any]]:
    """Build valid low-quality chapters when selector output cannot be repaired."""
```

Validation requires full coverage and internal end times from candidate times. Fallback greedily selects high-score candidates that satisfy min chapter duration, otherwise emits one full-video chapter.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_parse_selector_result_requires_candidate_boundaries_and_full_coverage -q`

Expected: PASS.

## Task 4: Workflow Pipeline

**Files:**
- Modify: `tests/test_story_chapter_workflow.py`
- Modify: `pipelines/story_chapter/workflow.py`
- Modify: `pipelines/story_chapter/__init__.py`

- [ ] **Step 1: Write failing end-to-end fake-client test**

Test should instantiate `StoryChapterWorkflowPipeline` with fake clients and fake frame extractor, then assert:

- `story_chapters.json` exists;
- `generation_mode == "workflow_candidate_mllm_selector"`;
- `boundary_candidates` is non-empty;
- selector prompt contains `FULL_UTTERANCE_TIMELINE`;
- selector image count is less than or equal to configured candidate-local frame budget.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_workflow_pipeline_writes_candidate_selector_artifact -q`

Expected: FAIL because pipeline class is missing.

- [ ] **Step 3: Implement `StoryChapterWorkflowPipeline`**

`run()` signature:

```python
def run(
    *,
    video_id: str,
    video_path: Path,
    video_metadata: dict[str, Any],
    transcription_path: Path,
    scene_detection_path: Path,
    output_root: Path,
) -> Path:
    """Run the full workflow and write story_chapters.json."""
```

Workflow:

1. Load utterances and scenes.
2. Recall rule candidates.
3. Score topic shifts with text LLM.
4. Select top-N candidates.
5. Extract frames at `t-1/t/t+1`.
6. Call MLLM selector with full subtitles and local frames.
7. Validate or fallback.
8. Write artifact.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_story_chapter_workflow.py::StoryChapterWorkflowTest::test_workflow_pipeline_writes_candidate_selector_artifact -q`

Expected: PASS.

## Task 5: CLI and Batch Scripts

**Files:**
- Create: `scripts/run_story_chapter_workflow.py`
- Create: `scripts/run_story_chapter_workflow_batch.py`
- Create: `scripts/algorithm/story_chapter/run_workflow.py`
- Create: `scripts/algorithm/story_chapter/run_workflow_batch.py`
- Create: `tests/test_story_chapter_workflow_script.py`
- Create: `tests/test_story_chapter_workflow_batch_script.py`

- [ ] **Step 1: Write failing script tests**

Tests should mirror existing multimodal script tests:

- `python scripts/algorithm/story_chapter/run_workflow.py --help` returns 0 and prints workflow description.
- batch discovery requires `video.mp4`, `video.transcription.json`, and `scene_detection.json`.
- batch `main()` accepts fake pipeline and writes `story_chapter_workflow_batch_summary.json`.

- [ ] **Step 2: Run script tests to verify they fail**

Run: `pytest tests/test_story_chapter_workflow_script.py tests/test_story_chapter_workflow_batch_script.py -q`

Expected: FAIL because scripts are missing.

- [ ] **Step 3: Implement scripts**

Single CLI args:

```text
video_id
--video
--transcription
--scene-detection
--output-root
--env-file
--top-candidates
--candidate-frame-offset-seconds
--frame-max-height
```

Batch CLI args:

```text
--dataset-root
--output-root
--env-file
--limit
--only-missing
--series-id
--episode-id
--top-candidates
--candidate-frame-offset-seconds
--frame-max-height
```

- [ ] **Step 4: Run script tests to verify they pass**

Run: `pytest tests/test_story_chapter_workflow_script.py tests/test_story_chapter_workflow_batch_script.py -q`

Expected: PASS.

## Task 6: Focused Regression and Full Tests

**Files:**
- All modified files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_story_chapter_workflow.py tests/test_story_chapter_workflow_script.py tests/test_story_chapter_workflow_batch_script.py tests/test_story_chapter_generation.py tests/test_story_chapter_generation_multimodal.py -q
```

Expected: PASS.

- [ ] **Step 2: Commit implementation**

Commit message:

```bash
git commit -m "feat: add efficient story chapter workflow"
```

## Task 7: Run Beiwang Episodes and Iterate Twice

**Files:**
- Output artifacts under `output/story_chapter_workflow_validation`.

- [ ] **Step 1: Locate beiwang episode inputs**

Use dataset discovery or `find /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm -maxdepth 4 -type f | rg 'beiwang|ep01|ep02'`.

- [ ] **Step 2: Run workflow on beiwang ep01 and ep02**

Run batch with explicit filters:

```bash
python scripts/algorithm/story_chapter/run_workflow_batch.py \
  --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/story_chapter_workflow_validation \
  --series-id beiwang \
  --episode-id ep01
```

Repeat for `ep02`, or use multiple ids if implemented.

- [ ] **Step 3: Evaluate results**

Inspect:

- chapter count;
- gaps/overlaps;
- whether titles are concrete;
- whether selected boundaries align with candidate evidence;
- MLLM frame count compared with baseline.

- [ ] **Step 4: Improvement round 1**

Adjust thresholds, prompt constraints, top-N, or postprocess based on output issues. Re-run focused tests and both episodes.

- [ ] **Step 5: Improvement round 2**

Repeat evaluation and one more targeted improvement. Re-run focused tests and both episodes.

- [ ] **Step 6: Final verification**

Run focused tests and check final output JSON files for both episodes.

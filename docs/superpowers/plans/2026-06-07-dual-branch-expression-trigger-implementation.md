# Dual Branch Expression Trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-branch expression trigger workflow that separates plot-structure candidates, punchline candidates, and final Triggerability ranking into a clean `trigger_time` asset.

**Architecture:** Add focused modules under `pipelines/expression_trigger/`: `plot_beats.py`, `punchlines.py`, `triggerability.py`, and `dual_branch_workflow.py`. Keep the legacy `workflow.py` available for comparison while updating the batch script, evaluator, and review tool to understand `trigger_time`.

**Tech Stack:** Python 3, existing `LlmClientProtocol`, existing subtitle/video utilities in `pipelines.utils`, pytest, local JSON outputs.

---

## File Structure

- Create `pipelines/expression_trigger/plot_beats.py`
  - Builds the Plot Beat Branch prompt.
  - Parses high-recall plot candidates with `start_time`, `end_time`, `trigger_time`, `candidate_type`, and evidence.

- Create `pipelines/expression_trigger/punchlines.py`
  - Builds the Punchline Branch prompt.
  - Parses non-plot punchline candidates, always as `笑点` candidates.

- Create `pipelines/expression_trigger/triggerability.py`
  - Builds the Triggerability Judge prompt.
  - Parses keep/reject decisions.
  - Applies deterministic top-k and gap de-duplication after LLM scoring.

- Create `pipelines/expression_trigger/dual_branch_workflow.py`
  - Orchestrates subtitles, duration probing, frame extraction, Plot Beat Branch, Punchline Branch, Triggerability Judge, and final trigger assembly.
  - Exposes `DualBranchExpressionTriggerPipeline` with a result object shaped like the legacy workflow result.

- Modify `scripts/run_workflow_expression_trigger_detection_batch.py`
  - Add `--pipeline legacy|dual_branch`.
  - Default to `dual_branch`.
  - Emit final clean assets with `trigger_time`.
  - Keep debug payloads with branch candidates and triggerability decisions.

- Modify `scripts/evaluate_expression_trigger_annotations.py`
  - Read `trigger_time` first, then fall back to `cue_time` and `payoff_time`.
  - Count `震惊` gold as unsupported for four-class expression accuracy.

- Modify `scripts/serve_algorithm_review_tool.py` and `apps/algorithm-review-tool/review_tool.js`
  - Display and seek predictions using `trigger_time` when present.
  - Fall back to old `cue_time` for legacy outputs.

- Add tests:
  - `tests/test_expression_trigger_plot_beats.py`
  - `tests/test_expression_trigger_punchlines.py`
  - `tests/test_expression_trigger_triggerability.py`
  - `tests/test_dual_branch_expression_trigger_workflow.py`
  - Extend `tests/test_workflow_expression_trigger_detection_batch_script.py`
  - Extend `tests/test_evaluate_expression_trigger_annotations.py`
  - Extend `tests/test_algorithm_review_tool_logic.py`
  - Extend `tests/test_algorithm_review_tool_server.py`

## Task 1: Plot Beat Candidate Parser

**Files:**
- Create: `pipelines/expression_trigger/plot_beats.py`
- Test: `tests/test_expression_trigger_plot_beats.py`

- [ ] **Step 1: Write parser tests**

Add `tests/test_expression_trigger_plot_beats.py`:

```python
from pipelines.expression_trigger.plot_beats import (
    build_plot_beat_prompt,
    parse_plot_beat_candidates,
)


def test_parse_plot_beat_candidates_keeps_valid_candidate() -> None:
    raw = {
        "plot_candidates": [
            {
                "candidate_id": "ignored_by_parser",
                "candidate_type": "payback",
                "start_time": 58.0,
                "end_time": 72.0,
                "trigger_time": 67.0,
                "summary": "女主掀桌反击。",
                "setup": "儿子被嫂子刁难。",
                "turning_point": "女主到场掀桌。",
                "payoff": "被欺负的一方夺回主动权。",
                "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
            }
        ]
    }

    candidates = parse_plot_beat_candidates(raw, video_id="jialijiawai_ep02", duration_sec=300.0)

    assert candidates == [
        {
            "candidate_id": "plot_jialijiawai_ep02_001",
            "source_branch": "plot_beat",
            "candidate_type": "payback",
            "start_time": 58.0,
            "end_time": 72.0,
            "trigger_time": 67.0,
            "summary": "女主掀桌反击。",
            "setup": "儿子被嫂子刁难。",
            "turning_point": "女主到场掀桌。",
            "payoff": "被欺负的一方夺回主动权。",
            "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
        }
    ]


def test_parse_plot_beat_candidates_rejects_invalid_type_and_time() -> None:
    raw = {
        "plot_candidates": [
            {"candidate_type": "random", "start_time": 1.0, "end_time": 2.0, "trigger_time": 1.5},
            {"candidate_type": "payback", "start_time": 3.0, "end_time": 2.0, "trigger_time": 2.5},
            {"candidate_type": "payback", "start_time": 1.0, "end_time": 4.0, "trigger_time": 8.0},
        ]
    }

    assert parse_plot_beat_candidates(raw, video_id="demo_ep01", duration_sec=10.0) == []


def test_build_plot_beat_prompt_contains_branch_contract() -> None:
    prompt = build_plot_beat_prompt(
        video_id="demo_ep01",
        video_duration_seconds=120.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\\n[1.000-2.000] 你凭啥子\\n[/SUBTITLE_TIMELINE]",
        metadata={"series": "demo"},
        frame_timestamps_seconds=[0.0, 10.0],
    )

    assert "Plot Beat Branch" in prompt
    assert "conflict_start" in prompt
    assert "trigger_time" in prompt
    assert "plot_candidates" in prompt
```

- [ ] **Step 2: Run parser tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_expression_trigger_plot_beats.py -q
```

Expected: fails with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Implement `plot_beats.py`**

Create `pipelines/expression_trigger/plot_beats.py`:

```python
from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.candidates import _format_frame_timestamps, _metadata_block


PLOT_BEAT_TYPES = {
    "conflict_start",
    "conflict_escalation",
    "face_slap",
    "payback",
    "reversal",
    "rescue_success",
    "relationship_advance",
    "family_emotional_payoff",
}


def build_plot_beat_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
    frame_timestamps_seconds: list[float],
) -> str:
    return "\n".join(
        [
            "## TASK",
            "You are the Plot Beat Branch of an expression-trigger pipeline.",
            "Find story-structure candidate intervals in a short-drama episode.",
            "Do not decide final expression triggers. Only output plot candidates.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            f"FRAME_TIMESTAMPS_SECONDS: {_format_frame_timestamps(frame_timestamps_seconds)}",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## CANDIDATE_TYPES",
            ", ".join(sorted(PLOT_BEAT_TYPES)),
            "",
            "## RULES",
            "- A candidate is a semantic time range, not a single point.",
            "- Use `start_time` for the required context start.",
            "- Use `end_time` for the semantic interval end.",
            "- Use `trigger_time` for the best possible expression trigger point if later accepted.",
            "- Include conflict starts and escalations when important, even if they may later be rejected.",
            "- Prefer recall over precision, but every candidate must be grounded in subtitles or frames.",
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `plot_candidates`.",
            "Each candidate must contain exactly these keys: `candidate_type`, `start_time`, `end_time`, `trigger_time`, `summary`, `setup`, `turning_point`, `payoff`, `evidence`.",
            "Output shape:",
            json.dumps(
                {
                    "plot_candidates": [
                        {
                            "candidate_type": "payback",
                            "start_time": 58.0,
                            "end_time": 72.0,
                            "trigger_time": 67.0,
                            "summary": "女主掀桌反击。",
                            "setup": "儿子被嫂子刁难。",
                            "turning_point": "女主到场掀桌。",
                            "payoff": "被欺负的一方夺回主动权。",
                            "evidence": ["64.790-67.190 你在我家吃饭，走就走了！"],
                        }
                    ]
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "",
            "## SUBTITLE_TIMELINE",
            subtitles_timeline,
        ]
    )


def _iter_plot_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("plot_candidates"), list):
        return raw["plot_candidates"]
    if isinstance(raw, list):
        return raw
    return []


def _evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def parse_plot_beat_candidates(raw: Any, *, video_id: str, duration_sec: float) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _iter_plot_items(raw):
        if not isinstance(item, dict):
            continue
        candidate_type = _clean_text(item.get("candidate_type"))
        if candidate_type not in PLOT_BEAT_TYPES:
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            trigger_time = float(item["trigger_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if trigger_time < start_time or trigger_time > end_time:
            continue
        if duration_sec > 0 and end_time > duration_sec:
            continue
        candidates.append(
            {
                "candidate_id": f"plot_{video_id}_{len(candidates) + 1:03d}",
                "source_branch": "plot_beat",
                "candidate_type": candidate_type,
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "trigger_time": _round_time(trigger_time),
                "summary": _clean_text(item.get("summary")),
                "setup": _clean_text(item.get("setup")),
                "turning_point": _clean_text(item.get("turning_point")),
                "payoff": _clean_text(item.get("payoff")),
                "evidence": _evidence_list(item.get("evidence")),
            }
        )
    return candidates


__all__ = [
    "PLOT_BEAT_TYPES",
    "build_plot_beat_prompt",
    "parse_plot_beat_candidates",
]
```

- [ ] **Step 4: Run parser tests and confirm they pass**

Run:

```bash
python -m pytest tests/test_expression_trigger_plot_beats.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add pipelines/expression_trigger/plot_beats.py tests/test_expression_trigger_plot_beats.py
git commit -m "feat: add plot beat candidate parser"
```

## Task 2: Punchline Candidate Parser

**Files:**
- Create: `pipelines/expression_trigger/punchlines.py`
- Test: `tests/test_expression_trigger_punchlines.py`

- [ ] **Step 1: Write punchline tests**

Add `tests/test_expression_trigger_punchlines.py`:

```python
from pipelines.expression_trigger.punchlines import build_punchline_prompt, parse_punchline_candidates


def test_parse_punchline_candidates_sets_laugh_expression() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 59.83,
                "end_time": 68.15,
                "trigger_time": 64.75,
                "summary": "女主用口水帮领导消毒形成笑点。",
                "setup": "领导夸张担心毒素进脑壳。",
                "punchline": "来嘛，我帮你消毒！",
                "payoff": "夸张担心和女主反制形成喜剧反差。",
                "evidence": ["63.430-64.750 来嘛，我帮你消毒！"],
            }
        ]
    }

    candidates = parse_punchline_candidates(raw, video_id="jialijiawai_ep01", duration_sec=220.0)

    assert candidates[0]["candidate_id"] == "punchline_jialijiawai_ep01_001"
    assert candidates[0]["source_branch"] == "punchline"
    assert candidates[0]["candidate_type"] == "punchline"
    assert candidates[0]["expression_type"] == "笑点"
    assert candidates[0]["trigger_time"] == 64.75


def test_parse_punchline_candidates_rejects_missing_punchline_text() -> None:
    raw = {
        "punchline_candidates": [
            {
                "start_time": 1.0,
                "end_time": 4.0,
                "trigger_time": 3.0,
                "summary": "普通剧情",
                "setup": "",
                "punchline": "",
                "payoff": "",
                "evidence": [],
            }
        ]
    }

    assert parse_punchline_candidates(raw, video_id="demo_ep01", duration_sec=10.0) == []


def test_build_punchline_prompt_mentions_non_plot_boundary() -> None:
    prompt = build_punchline_prompt(
        video_id="demo_ep01",
        video_duration_seconds=120.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\\n[1.000-2.000] 哈哈\\n[/SUBTITLE_TIMELINE]",
        metadata={},
    )

    assert "Punchline Branch" in prompt
    assert "笑点" in prompt
    assert "Do not output plot payback" in prompt
```

- [ ] **Step 2: Run punchline tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_expression_trigger_punchlines.py -q
```

Expected: fails with missing module.

- [ ] **Step 3: Implement `punchlines.py`**

Create `pipelines/expression_trigger/punchlines.py`:

```python
from __future__ import annotations

import json
from typing import Any

from pipelines.expression_trigger.baseline_mllm import _clean_text, _round_time
from pipelines.expression_trigger.candidates import _metadata_block


def build_punchline_prompt(
    *,
    video_id: str,
    video_duration_seconds: float,
    subtitles_timeline: str,
    metadata: dict[str, Any] | None,
) -> str:
    return "\n".join(
        [
            "## TASK",
            "You are the Punchline Branch of an expression-trigger pipeline.",
            "Find non-plot-structure comedy moments where viewers would naturally react with 笑点.",
            "Do not output plot payback, romance, tear, shock, or generic light tone.",
            "",
            "## INPUT",
            f"VIDEO_ID: {video_id}",
            f"VIDEO_DURATION_SECONDS: {video_duration_seconds:.3f}",
            "[METADATA]",
            _metadata_block(metadata),
            "[/METADATA]",
            "",
            "## RULES",
            "- A punchline candidate must contain a setup and a clear punchline or comic reversal.",
            "- It can come from dialogue, dialect, exaggerated wording, awkward reversal, misunderstanding, or action plus dialogue.",
            "- Use `trigger_time` at the moment the joke becomes understandable.",
            "- Reject ordinary plot conflict, ordinary cute tone, and vague funny atmosphere.",
            "",
            "## OUTPUT",
            "Return JSON only. The top-level object must contain exactly one key: `punchline_candidates`.",
            "Each candidate must contain exactly these keys: `start_time`, `end_time`, `trigger_time`, `summary`, `setup`, `punchline`, `payoff`, `evidence`.",
            json.dumps(
                {
                    "punchline_candidates": [
                        {
                            "start_time": 59.83,
                            "end_time": 68.15,
                            "trigger_time": 64.75,
                            "summary": "女主用口水帮领导消毒形成笑点。",
                            "setup": "领导夸张担心毒素进脑壳。",
                            "punchline": "来嘛，我帮你消毒！",
                            "payoff": "夸张担心和女主反制形成喜剧反差。",
                            "evidence": ["63.430-64.750 来嘛，我帮你消毒！"],
                        }
                    ]
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "",
            "## SUBTITLE_TIMELINE",
            subtitles_timeline,
        ]
    )


def _iter_punchline_items(raw: Any) -> list[Any]:
    if isinstance(raw, dict) and isinstance(raw.get("punchline_candidates"), list):
        return raw["punchline_candidates"]
    if isinstance(raw, list):
        return raw
    return []


def _evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def parse_punchline_candidates(raw: Any, *, video_id: str, duration_sec: float) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _iter_punchline_items(raw):
        if not isinstance(item, dict):
            continue
        try:
            start_time = float(item["start_time"])
            end_time = float(item["end_time"])
            trigger_time = float(item["trigger_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0.0 or end_time <= start_time:
            continue
        if trigger_time < start_time or trigger_time > end_time:
            continue
        if duration_sec > 0 and end_time > duration_sec:
            continue
        punchline = _clean_text(item.get("punchline"))
        payoff = _clean_text(item.get("payoff"))
        if not punchline or not payoff:
            continue
        candidates.append(
            {
                "candidate_id": f"punchline_{video_id}_{len(candidates) + 1:03d}",
                "source_branch": "punchline",
                "candidate_type": "punchline",
                "expression_type": "笑点",
                "start_time": _round_time(start_time),
                "end_time": _round_time(end_time),
                "trigger_time": _round_time(trigger_time),
                "summary": _clean_text(item.get("summary")),
                "setup": _clean_text(item.get("setup")),
                "punchline": punchline,
                "payoff": payoff,
                "evidence": _evidence_list(item.get("evidence")),
            }
        )
    return candidates


__all__ = [
    "build_punchline_prompt",
    "parse_punchline_candidates",
]
```

- [ ] **Step 4: Run punchline tests and confirm they pass**

Run:

```bash
python -m pytest tests/test_expression_trigger_punchlines.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit Task 2**

```bash
git add pipelines/expression_trigger/punchlines.py tests/test_expression_trigger_punchlines.py
git commit -m "feat: add punchline candidate parser"
```

## Task 3: Triggerability Judge Parser and Top-K

**Files:**
- Create: `pipelines/expression_trigger/triggerability.py`
- Test: `tests/test_expression_trigger_triggerability.py`

- [ ] **Step 1: Write Triggerability tests**

Add `tests/test_expression_trigger_triggerability.py` with tests covering:

```python
from pipelines.expression_trigger.triggerability import (
    build_triggerability_prompt,
    parse_triggerability_decisions,
    select_top_expression_triggers,
)


def test_parse_triggerability_decisions_keeps_valid_decision() -> None:
    candidates = [
        {
            "candidate_id": "plot_demo_ep01_001",
            "source_branch": "plot_beat",
            "candidate_type": "payback",
            "start_time": 10.0,
            "end_time": 20.0,
            "trigger_time": 18.0,
            "summary": "女主打脸反派。",
        }
    ]
    raw = {
        "triggerability_decisions": [
            {
                "candidate_id": "plot_demo_ep01_001",
                "decision": "keep",
                "expression_type": "爽点",
                "importance_score": 0.91,
                "start_time": 10.0,
                "end_time": 20.0,
                "trigger_time": 18.5,
                "reason": "反击完成，解气明确。",
                "rank_reason": "本集强爽点。",
            }
        ]
    }

    decisions = parse_triggerability_decisions(raw, candidates=candidates)

    assert decisions[0]["decision"] == "keep"
    assert decisions[0]["expression_type"] == "爽点"
    assert decisions[0]["trigger_time"] == 18.5


def test_parse_triggerability_decisions_rejects_unsupported_expression() -> None:
    candidates = [{"candidate_id": "plot_demo_ep01_001", "start_time": 1.0, "end_time": 3.0, "trigger_time": 2.0}]
    raw = {
        "triggerability_decisions": [
            {
                "candidate_id": "plot_demo_ep01_001",
                "decision": "keep",
                "expression_type": "震惊",
                "importance_score": 0.9,
                "start_time": 1.0,
                "end_time": 3.0,
                "trigger_time": 2.0,
                "reason": "突然。",
                "rank_reason": "意外。",
            }
        ]
    }

    assert parse_triggerability_decisions(raw, candidates=candidates)[0]["decision"] == "reject"


def test_select_top_expression_triggers_applies_score_and_gap() -> None:
    decisions = [
        {
            "candidate_id": "a",
            "decision": "keep",
            "expression_type": "爽点",
            "importance_score": 0.80,
            "start_time": 10.0,
            "end_time": 20.0,
            "trigger_time": 18.0,
            "reason": "弱一点。",
        },
        {
            "candidate_id": "b",
            "decision": "keep",
            "expression_type": "爽点",
            "importance_score": 0.95,
            "start_time": 22.0,
            "end_time": 30.0,
            "trigger_time": 28.0,
            "reason": "同类更强。",
        },
        {
            "candidate_id": "c",
            "decision": "keep",
            "expression_type": "笑点",
            "importance_score": 0.70,
            "start_time": 60.0,
            "end_time": 66.0,
            "trigger_time": 64.0,
            "reason": "笑点。",
        },
    ]

    triggers = select_top_expression_triggers(decisions, video_id="demo_ep01", top_k=4, min_gap_seconds=20.0)

    assert [trigger["candidate_id"] for trigger in triggers] == ["b", "c"]
    assert triggers[0]["trigger_id"] == "et_demo_ep01_001"


def test_build_triggerability_prompt_contains_topk_contract() -> None:
    prompt = build_triggerability_prompt(
        video_id="demo_ep01",
        video_duration_seconds=100.0,
        subtitles_timeline="[SUBTITLE_TIMELINE]\\n[/SUBTITLE_TIMELINE]",
        candidates=[{"candidate_id": "a", "summary": "x"}],
        top_k=4,
        min_gap_seconds=20.0,
    )

    assert "Triggerability Judge" in prompt
    assert "top_k=4" in prompt
    assert "trigger_time" in prompt
```

- [ ] **Step 2: Run Triggerability tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_expression_trigger_triggerability.py -q
```

Expected: fails with missing module.

- [ ] **Step 3: Implement `triggerability.py`**

Implement:

- `SUPPORTED_FINAL_EXPRESSIONS = {"爽点", "甜点", "泪点", "笑点"}`
- `build_triggerability_prompt(...)`
- `parse_triggerability_decisions(...)`
- `select_top_expression_triggers(...)`

Use this deterministic behavior:

- Unknown `candidate_id` is ignored.
- Unsupported `expression_type` forces `decision="reject"`.
- Invalid times force `decision="reject"`.
- Missing LLM decision creates a reject decision for that candidate with reason `missing triggerability decision`.
- `select_top_expression_triggers` sorts keep decisions by `importance_score` descending, applies same-expression gap de-duplication, keeps top-k, then returns items sorted by `trigger_time`.
- Final trigger fields: `trigger_id`, `video_id`, `candidate_id`, `source_branch`, `candidate_type`, `start_time`, `end_time`, `trigger_time`, `expression_type`, `importance_score`, `summary`, `reason`.

- [ ] **Step 4: Run Triggerability tests and confirm they pass**

Run:

```bash
python -m pytest tests/test_expression_trigger_triggerability.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 3**

```bash
git add pipelines/expression_trigger/triggerability.py tests/test_expression_trigger_triggerability.py
git commit -m "feat: add triggerability judge selection"
```

## Task 4: Dual Branch Workflow Orchestration

**Files:**
- Create: `pipelines/expression_trigger/dual_branch_workflow.py`
- Test: `tests/test_dual_branch_expression_trigger_workflow.py`

- [ ] **Step 1: Write workflow tests with a fake LLM client**

Add tests that define a fake client returning three responses in order:

1. Plot candidates;
2. Punchline candidates;
3. Triggerability decisions.

The test should create a temporary SRT and fake video path, monkeypatch `probe_video_duration_seconds` to return `120.0`, and monkeypatch `extract_frames_at_timestamps` to avoid ffmpeg.

Assertions:

- `result.plot_candidates` contains plot items.
- `result.punchline_candidates` contains punchline items.
- `result.triggerability_decisions` contains decisions.
- `result.expression_triggers` contains top-k final triggers with `trigger_time`.
- `result.resonance_cues` is empty for dual-branch first version because final assets no longer need `ui_trigger_time`.

- [ ] **Step 2: Run workflow tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_dual_branch_expression_trigger_workflow.py -q
```

Expected: fails with missing `DualBranchExpressionTriggerPipeline`.

- [ ] **Step 3: Implement `dual_branch_workflow.py`**

Implementation outline:

```python
@dataclass(frozen=True)
class DualBranchExpressionTriggerResult:
    plot_candidates: list[dict[str, Any]]
    punchline_candidates: list[dict[str, Any]]
    expression_candidates: list[dict[str, Any]]
    triggerability_decisions: list[dict[str, Any]]
    candidate_decisions: list[dict[str, Any]]
    expression_triggers: list[dict[str, Any]]
    resonance_cues: list[dict[str, Any]]
    llm_calls: dict[str, dict[str, Any]]
```

`DualBranchExpressionTriggerPipeline.__init__` should accept:

- `llm_client`
- `sample_interval_sec=10.0`
- `max_frames=None`
- `frame_max_height=512`
- `top_k=4`
- `min_gap_seconds=20.0`
- `branch_max_output_tokens=2400`
- `judge_max_output_tokens=2400`
- `progress_callback=None`

`run(...)` should:

1. load subtitles;
2. probe duration;
3. build timeline;
4. build frame timestamps using existing `build_sample_timestamps`;
5. extract frames once for Plot Beat Branch;
6. call Plot Beat Branch multimodal LLM;
7. call Punchline Branch text or multimodal LLM using no images in first version;
8. merge candidates;
9. call Triggerability Judge;
10. select final triggers;
11. return result.

- [ ] **Step 4: Run workflow tests and confirm they pass**

Run:

```bash
python -m pytest tests/test_dual_branch_expression_trigger_workflow.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add pipelines/expression_trigger/dual_branch_workflow.py tests/test_dual_branch_expression_trigger_workflow.py
git commit -m "feat: add dual branch expression workflow"
```

## Task 5: Batch Script Pipeline Selection and `trigger_time` Assets

**Files:**
- Modify: `scripts/run_workflow_expression_trigger_detection_batch.py`
- Test: `tests/test_workflow_expression_trigger_detection_batch_script.py`

- [ ] **Step 1: Add failing batch tests**

Add tests for:

- parser accepts `--pipeline dual_branch` and `--pipeline legacy`;
- default parser value is `dual_branch`;
- `build_pipeline(..., pipeline_type="dual_branch")` returns `DualBranchExpressionTriggerPipeline`;
- `write_workflow_episode_output` writes final asset item with `trigger_time` and without `cue_time` or `ui_trigger_time` for dual-branch triggers;
- debug payload includes `plot_candidates`, `punchline_candidates`, and `triggerability_decisions` when present on the result object.

- [ ] **Step 2: Run batch tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_workflow_expression_trigger_detection_batch_script.py -q
```

Expected: new tests fail before implementation.

- [ ] **Step 3: Modify batch script**

Changes:

- Add `parser.add_argument("--pipeline", choices=("dual_branch", "legacy"), default="dual_branch")`.
- Rename existing `build_pipeline` import path to the actual package path:
  - legacy: `from pipelines.expression_trigger.workflow import WorkflowExpressionTriggerPipeline`
  - dual branch: `from pipelines.expression_trigger.dual_branch_workflow import DualBranchExpressionTriggerPipeline`
- Add `pipeline_type` parameter to `build_pipeline`.
- Map legacy params to legacy pipeline and dual params to dual pipeline.
- Update asset serialization:
  - If trigger has `trigger_time`, write `trigger_time`.
  - Else write legacy `cue_time` for legacy output compatibility only when `pipeline_type == "legacy"`.
- Debug payload:
  - Always include `expression_candidates`.
  - Include optional `plot_candidates`, `punchline_candidates`, `triggerability_decisions` if the result object exposes them.

- [ ] **Step 4: Run batch tests and confirm they pass**

Run:

```bash
python -m pytest tests/test_workflow_expression_trigger_detection_batch_script.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add scripts/run_workflow_expression_trigger_detection_batch.py tests/test_workflow_expression_trigger_detection_batch_script.py
git commit -m "feat: route workflow batch to dual branch pipeline"
```

## Task 6: Evaluation and Review Tool Compatibility

**Files:**
- Modify: `scripts/evaluate_expression_trigger_annotations.py`
- Modify: `scripts/serve_algorithm_review_tool.py`
- Modify: `apps/algorithm-review-tool/review_tool.js`
- Test: `tests/test_evaluate_expression_trigger_annotations.py`
- Test: `tests/test_algorithm_review_tool_server.py`
- Test: `tests/test_algorithm_review_tool_logic.py`

- [ ] **Step 1: Add failing compatibility tests**

Evaluation tests:

- prediction with `trigger_time` matches gold `cue_time`;
- prediction with legacy `cue_time` still matches;
- gold `primary_expression="震惊"` is reported as unsupported and excluded from four-class expression accuracy.

Server tests:

- algorithm output loader exposes `trigger_time` for prediction items;
- legacy output with `cue_time` still loads.

Frontend logic tests:

- prediction normalization uses `trigger_time` first;
- clicking prediction still seeks to the normalized time.

- [ ] **Step 2: Run compatibility tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_evaluate_expression_trigger_annotations.py tests/test_algorithm_review_tool_server.py tests/test_algorithm_review_tool_logic.py -q
```

Expected: new tests fail.

- [ ] **Step 3: Implement compatibility**

Evaluation:

- Update `_time_value(item)` to check `trigger_time`, then `payoff_time`, then `cue_time`.
- Add unsupported gold handling for `震惊`:
  - include `unsupported_gold_count`;
  - keep unsupported items visible in report;
  - exclude unsupported labels from four-class expression accuracy denominator.

Server:

- Normalize prediction items with `trigger_time = item.trigger_time ?? item.cue_time ?? item.payoff_time`.

Frontend:

- Normalize prediction timestamp using the same precedence.
- Keep display label as `trigger_time` for new outputs.

- [ ] **Step 4: Run compatibility tests and confirm they pass**

Run:

```bash
python -m pytest tests/test_evaluate_expression_trigger_annotations.py tests/test_algorithm_review_tool_server.py tests/test_algorithm_review_tool_logic.py -q
```

Expected: all tests pass, except any existing sandbox-only HTTP binding test should be run selectively if needed.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/evaluate_expression_trigger_annotations.py scripts/serve_algorithm_review_tool.py apps/algorithm-review-tool/review_tool.js tests/test_evaluate_expression_trigger_annotations.py tests/test_algorithm_review_tool_server.py tests/test_algorithm_review_tool_logic.py
git commit -m "feat: support trigger_time in expression trigger tools"
```

## Task 7: End-to-End Smoke With Fake Pipeline and Real CLI

**Files:**
- Modify: tests only if needed
- Test: existing focused suites

- [ ] **Step 1: Run full focused test set**

Run:

```bash
python -m pytest \
  tests/test_expression_trigger_plot_beats.py \
  tests/test_expression_trigger_punchlines.py \
  tests/test_expression_trigger_triggerability.py \
  tests/test_dual_branch_expression_trigger_workflow.py \
  tests/test_workflow_expression_trigger_detection_batch_script.py \
  tests/test_evaluate_expression_trigger_annotations.py \
  tests/test_algorithm_review_tool_logic.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Python compile check**

Run:

```bash
python -m py_compile \
  pipelines/expression_trigger/plot_beats.py \
  pipelines/expression_trigger/punchlines.py \
  pipelines/expression_trigger/triggerability.py \
  pipelines/expression_trigger/dual_branch_workflow.py \
  scripts/run_workflow_expression_trigger_detection_batch.py \
  scripts/evaluate_expression_trigger_annotations.py \
  scripts/serve_algorithm_review_tool.py
```

Expected: exits 0 with no output.

- [ ] **Step 3: Inspect final git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only files from this plan are modified.

- [ ] **Step 4: Commit final integration if there are uncommitted verification-only changes**

If Task 1-6 commits already include all code, skip this step. If Task 7 required small test or compatibility fixes, commit:

```bash
git add <changed-files>
git commit -m "test: verify dual branch expression trigger workflow"
```

## Self-Review Checklist

- Spec coverage:
  - dual branch: Tasks 1, 2, 4;
  - Triggerability responsibilities: Task 3;
  - top-k and `min_gap_seconds`: Task 3;
  - single `trigger_time`: Tasks 3, 5, 6;
  - final/debug asset split: Task 5;
  - evaluator/review compatibility: Task 6.

- Placeholder scan:
  - No task contains unresolved placeholder markers.
  - Every implementation task has exact target files and test commands.

- Type consistency:
  - Candidate fields are consistently `start_time`, `end_time`, `trigger_time`.
  - Final trigger fields are consistently `trigger_id`, `video_id`, `candidate_id`, `source_branch`, `candidate_type`, `start_time`, `end_time`, `trigger_time`, `expression_type`, `importance_score`, `summary`, `reason`.

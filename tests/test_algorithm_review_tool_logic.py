from __future__ import annotations

import subprocess
from pathlib import Path


def run_node(script: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        ["node", "-e", script],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_review_tool_normalizes_expression_triggers_and_highlight_assets() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const items = logic.normalizeAlgorithmOutput({
  expression_triggers: [
    {
      trigger_id: 'et_demo_001',
      start_time: 10,
      end_time: 13,
      cue_time: 11.5,
      source_type: 'plot',
      expression_type: '爽到了',
      interaction_mode: 'single_tap',
      confidence: 0.83,
      summary: '女主反击',
      reason: '压抑后的释放'
    }
  ],
  highlight_assets: [
    {
      highlight_id: 'h_demo_001',
      start_time: 20,
      end_time: 25,
      highlight_type: 'plot',
      emotion: '震惊',
      confidence: 0.7,
      summary: '身份揭晓',
      reason: '信息反转'
    }
  ]
}, 'demo_ep01');

if (items.length !== 1) throw new Error(`expected expression triggers to win, got ${items.length}`);
const item = items[0];
if (item.id !== 'et_demo_001') throw new Error('trigger id mismatch');
if (item.kind !== 'expression_trigger') throw new Error('kind mismatch');
if (item.cue_time !== 11.5) throw new Error('cue time mismatch');
if (item.primary_expression !== '爽到了') throw new Error('expression mismatch');
if (item.source_type !== 'plot') throw new Error('source type mismatch');
if (item.interaction_mode !== 'single_tap') throw new Error('interaction mode mismatch');
if (item.setup !== '') throw new Error('missing setup should normalize to empty string');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr


def test_review_tool_normalizes_expression_trigger_time() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const items = logic.normalizeAlgorithmOutput({
  expression_triggers: [
    {
      trigger_id: 'et_demo_001',
      start_time: 10,
      end_time: 13,
      trigger_time: 12.25,
      expression_type: '笑点',
      importance_score: 0.91,
      summary: '包袱落地',
      reason: '台词反差'
    }
  ]
}, 'demo_ep01');

const item = items[0];
if (item.cue_time !== 12.25) throw new Error(`trigger_time should normalize to cue_time, got ${item.cue_time}`);
if (item.raw.trigger_time !== 12.25) throw new Error('raw trigger_time missing');
if (item.primary_expression !== '笑点') throw new Error('expression mismatch');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr


def test_review_tool_normalizes_highlight_candidates_when_no_final_output_exists() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const items = logic.normalizeAlgorithmOutput({
  candidate_scene_cues: [
    {
      cue_id: 'cue_003',
      cue_time: 42.25,
      context_start_time: 39,
      context_end_time: 45,
      context_subtitles: '[42.000-43.000] 你到底是谁'
    }
  ]
}, 'demo_ep01');

if (items.length !== 1) throw new Error(`expected one cue, got ${items.length}`);
const item = items[0];
if (item.id !== 'cue_003') throw new Error('cue id mismatch');
if (item.kind !== 'highlight_candidate') throw new Error('kind mismatch');
if (item.start_time !== 39 || item.end_time !== 45 || item.cue_time !== 42.25) throw new Error('time mismatch');
if (!item.summary.includes('你到底是谁')) throw new Error(`summary mismatch: ${item.summary}`);
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr


def test_review_tool_falls_back_to_candidate_cues() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const items = logic.normalizeAlgorithmOutput({
  candidate_cues: [
    {
      cue_id: 'cue_004',
      cue_time: 50,
      utterance: '你竟然骗我',
      highlight_type: 'conflict',
      summary: '冲突爆发',
      reason: '适合表达愤怒',
      confidence: 0.61
    }
  ]
}, 'demo_ep01');

if (items.length !== 1) throw new Error(`expected one cue, got ${items.length}`);
const item = items[0];
if (item.id !== 'cue_004') throw new Error('cue id mismatch');
if (item.source_type !== 'conflict') throw new Error('source type mismatch');
if (item.summary !== '冲突爆发') throw new Error(`summary mismatch: ${item.summary}`);
if (item.confidence !== 0.61) throw new Error('confidence mismatch');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr


def test_review_tool_normalizes_gold_annotations() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const items = logic.normalizeGoldAnnotations({
  annotations: [
    {
      annotation_id: 'gold_demo_001',
      cue_time: '12.3456',
      primary_expression: '笑点',
      reason: '这里是台词包袱。',
      payoff_window: { start_time: 11, end_time: 13.5 }
    }
  ]
}, 'demo_ep01');

if (items.length !== 1) throw new Error(`expected one gold annotation, got ${items.length}`);
const item = items[0];
if (item.id !== 'gold_demo_001') throw new Error('annotation id mismatch');
if (item.kind !== 'gold_annotation') throw new Error('kind mismatch');
if (item.cue_time !== 12.346) throw new Error(`cue time mismatch: ${item.cue_time}`);
if (item.primary_expression !== '笑点') throw new Error('expression mismatch');
if (item.reason !== '这里是台词包袱。') throw new Error('reason mismatch');
if (item.payoff_window.start_time !== 11 || item.payoff_window.end_time !== 13.5) throw new Error('window mismatch');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr


def test_review_tool_exports_comparison_only_helpers() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

if (typeof logic.normalizeAlgorithmOutput !== 'function') throw new Error('missing prediction normalizer');
if (typeof logic.normalizeGoldAnnotations !== 'function') throw new Error('missing gold normalizer');
if (typeof logic.buildFeedbackPayload !== 'undefined') throw new Error('feedback builder should be removed');
if (typeof logic.normalizeReviewMap !== 'undefined') throw new Error('review map normalizer should be removed');
if (typeof logic.normalizeMissedTriggers !== 'undefined') throw new Error('missed trigger normalizer should be removed');
if (typeof logic.VERDICTS !== 'undefined') throw new Error('verdict constants should be removed');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr


def test_review_tool_renders_prediction_groundtruth_comparison_only() -> None:
    html = Path("apps/algorithm-review-tool/index.html").read_text(encoding="utf-8")

    assert "/api/episodes/${videoId}/gold-annotations" in html
    assert "state.goldAnnotations" in html
    assert "groundtruthList" in html
    assert "predictionList" in html
    assert "Groundtruth" in html
    assert "Prediction" in html
    assert "marker gold" in html
    assert "renderComparisonLists" in html
    assert "renderSelectedDetail" in html
    assert "trigger-reason" in html
    assert "saveFeedback" not in html
    assert "addMissed" not in html
    assert "filterSelect" not in html
    assert "verdictButton" not in html
    assert "renderMissedEditor" not in html
    assert "buildFeedbackPayload" not in html
    assert "danmakuList" not in html


def test_review_tool_normalizes_release_structure_fields() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const items = logic.normalizeAlgorithmOutput({
  expression_triggers: [
    {
      trigger_id: 'et_demo_001',
      start_time: 10,
      end_time: 13,
      cue_time: 11.5,
      source_type: 'plot',
      primary_expression: '爽到了',
      confidence: 0.83,
      summary: '女主反击',
      setup: '女主此前被压制',
      turning_point: '女主当众反击',
      expression_release: '压抑释放形成爽感',
      reason: '这是情绪释放点'
    }
  ]
}, 'demo_ep01');

const item = items[0];
if (item.setup !== '女主此前被压制') throw new Error('setup mismatch');
if (item.turning_point !== '女主当众反击') throw new Error('turning point mismatch');
if (item.expression_release !== '压抑释放形成爽感') throw new Error('release mismatch');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr

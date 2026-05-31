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
      primary_expression: '爽到了',
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


def test_review_tool_builds_feedback_payload_with_reviews_and_missed_triggers() -> None:
    script = """
const logic = require('./apps/algorithm-review-tool/review_tool.js');

const payload = logic.buildFeedbackPayload({
  videoId: 'demo_ep01',
  datasetEpisodeDir: '/tmp/data/demo/ep01',
  algorithmOutputPath: 'output/demo_ep01/highlight_recognition.json',
  reviews: {
    et_demo_001: {
      verdict: 'timing_early',
      corrected_start_time: '12.3456',
      corrected_end_time: '15.2',
      corrected_primary_expression: '爽到了',
      corrected_interaction_mode: 'single_tap',
      note: '触发应稍微后移'
    }
  },
  missedTriggers: [
    {
      cue_time: '42.199',
      source_type: 'plot',
      primary_expression: '震惊',
      interaction_mode: 'single_tap',
      note: '身份反转漏检'
    }
  ],
  episodeReview: { status: 'done', note: '第一轮完成' }
});

if (payload.video_id !== 'demo_ep01') throw new Error('video_id mismatch');
if (payload.trigger_reviews.length !== 1) throw new Error('review count mismatch');
if (payload.trigger_reviews[0].corrected_start_time !== 12.346) throw new Error('rounded start mismatch');
if (payload.missed_triggers[0].missed_id !== 'missed_demo_ep01_001') throw new Error('missed id mismatch');
if (payload.missed_triggers[0].cue_time !== 42.199) throw new Error('missed time mismatch');
if (payload.episode_review.status !== 'done') throw new Error('episode status mismatch');
"""
    result = run_node(script)

    assert result.returncode == 0, result.stderr

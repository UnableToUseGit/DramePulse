from __future__ import annotations

import subprocess
from pathlib import Path


def test_annotation_tool_core_logic_exports_minimal_gold_payload() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = """
const logic = require('./apps/annotation-tool/annotation_tool.js');

const danmaku = logic.normalizeDanmaku([
  { time_sec: 0.5, text: '开场就上头', digg_count: 2, score: 4.5 },
  { time_ms: 2000, text: '这里反转了', digg_count: 9, score: 12 },
  { time_sec: 4.2, text: '后面才到', digg_count: 1, score: 1 },
]);

if (danmaku[1].time_sec !== 2) {
  throw new Error('time_ms should be normalized to time_sec');
}

const activeIndex = logic.findActiveDanmakuIndex(danmaku, 2.1);
if (activeIndex !== 1) {
  throw new Error(`expected active index 1, got ${activeIndex}`);
}

const payload = logic.buildAnnotationPayload({
  videoId: 'case1_ep01',
  videoPath: 'data/case1/ep01.mp4',
  subtitlePath: 'data/case1/ep01.srt',
  sourceJsonPath: 'data/case1/ep01.json',
  annotations: [
    {
      annotation_id: 'custom_id_should_be_replaced',
      cue_time: '8.96',
      primary_expression: '震惊',
      reason: '开场亲吻引发震惊和吐槽。',
      ignored: 'not exported',
    },
  ],
});

const annotation = payload.annotations[0];
if (payload.video_id !== 'case1_ep01') throw new Error('video_id mismatch');
if (annotation.annotation_id !== 'gold_case1_ep01_001') throw new Error('annotation_id mismatch');
if (annotation.cue_time !== 8.96) throw new Error('cue_time mismatch');
if ('start_time' in annotation || 'end_time' in annotation) throw new Error('unexpected range fields exported');
if (annotation.primary_expression !== '震惊') throw new Error('primary_expression mismatch');
if ('emotion' in annotation) throw new Error('legacy emotion field exported');
if (annotation.reason !== '开场亲吻引发震惊和吐槽。') throw new Error('reason mismatch');
if ('ignored' in annotation) throw new Error('unexpected extra field exported');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_annotation_tool_resolves_backend_video_context() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = """
const logic = require('./apps/annotation-tool/annotation_tool.js');

const config = logic.readAnnotationConfig(
  'http://127.0.0.1:8770/apps/annotation-tool/?video_id=ep_10&api_base_url=http://127.0.0.1:8000/'
);

if (config.videoId !== 'ep_10') throw new Error('video_id query param not read');
if (config.apiBaseUrl !== 'http://127.0.0.1:8000') throw new Error(`api_base_url not normalized: ${config.apiBaseUrl}`);
if (logic.buildApiUrl(config.apiBaseUrl, '/api/videos/ep_10') !== 'http://127.0.0.1:8000/api/videos/ep_10') {
  throw new Error('absolute API URL not built correctly');
}

const selected = logic.selectInitialVideo(
  [
    { video_id: 'ep_01', title: '第一集', stream_url: '/api/videos/ep_01/stream', danmaku_url: '/api/videos/ep_01/danmaku' },
    { video_id: 'ep_10', title: '第十集', stream_url: '/api/videos/ep_10/stream', danmaku_url: '/api/videos/ep_10/danmaku' },
  ],
  config.videoId
);

if (selected.video_id !== 'ep_10') throw new Error('requested video was not selected');

const context = logic.normalizeVideoContext(selected, config);
if (context.videoId !== 'ep_10') throw new Error('context videoId mismatch');
if (context.title !== '第十集') throw new Error('context title mismatch');
if (context.videoPath !== 'http://127.0.0.1:8000/api/videos/ep_10/stream') throw new Error(`videoPath mismatch: ${context.videoPath}`);
if (context.sourceJsonPath !== 'http://127.0.0.1:8000/api/videos/ep_10/danmaku') throw new Error(`sourceJsonPath mismatch: ${context.sourceJsonPath}`);
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_annotation_tool_resolves_algorithm_episode_context() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = """
const logic = require('./apps/annotation-tool/annotation_tool.js');

const config = logic.readAnnotationConfig(
  'http://127.0.0.1:8783/apps/annotation-tool/?video_id=beiwang_ep01'
);

const selected = logic.selectInitialVideo(
  logic.normalizeVideoList({
    episodes: [
      {
        video_id: 'beiwang_ep01',
        series_id: 'beiwang',
        episode_id: 'ep01',
        title: '北往 第1集',
        video_path: '/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beiwang/ep01/video.mp4',
        subtitle_path: '/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beiwang/ep01/video.srt',
      },
      { video_id: 'nanian_dongzhi_ep02', series_id: 'nanian_dongzhi', episode_id: 'ep02', title: '那年冬至 第2集' },
    ],
  }),
  config.videoId
);

if (selected.video_id !== 'beiwang_ep01') throw new Error('requested episode was not selected');

const context = logic.normalizeVideoContext(selected, config);
if (context.videoId !== 'beiwang_ep01') throw new Error('context videoId mismatch');
if (context.videoPath !== '/api/episodes/beiwang_ep01/video') throw new Error(`videoPath mismatch: ${context.videoPath}`);
if (context.sourceJsonPath !== '/api/episodes/beiwang_ep01/danmaku') throw new Error(`sourceJsonPath mismatch: ${context.sourceJsonPath}`);
if (context.subtitlePath !== '/api/episodes/beiwang_ep01/subtitle') throw new Error(`subtitlePath mismatch: ${context.subtitlePath}`);
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_annotation_tool_page_does_not_reference_static_case_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    html = (repo_root / "apps/annotation-tool/index.html").read_text(encoding="utf-8")

    assert "data/case1" not in html
    assert "case1_ep01" not in html
    assert "/api/videos" not in html
    assert "/api/episodes" in html


def test_annotation_tool_page_uses_single_cue_time_and_primary_expression_controls() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    html = (repo_root / "apps/annotation-tool/index.html").read_text(encoding="utf-8")

    assert 'id="cueTime"' in html
    assert 'id="markCue"' in html
    assert 'id="jumpCue"' in html
    assert "cue_time" in html
    assert 'id="primaryExpression"' in html
    assert "primary_expression" in html
    for expression in ("爽到了", "震惊", "磕到了", "看哭了", "燃起来了", "笑死"):
        assert f'value="{expression}"' in html
    for excluded in ("剧集喜爱", "共鸣了", "吐槽", "角色魅力"):
        assert excluded not in html
    assert 'id="emotion"' not in html
    assert 'id="startTime"' not in html
    assert 'id="endTime"' not in html
    assert 'id="markStart"' not in html
    assert 'id="markEnd"' not in html
    assert 'id="jumpStart"' not in html
    assert 'id="jumpEnd"' not in html

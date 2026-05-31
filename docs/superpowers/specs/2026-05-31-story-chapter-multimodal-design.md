# Story Chapter Multimodal 生成 Pipeline 设计记录

## 1. 背景

text-only `Story Chapter` 生成已经能基于字幕给出剧情导航章节，但验证后发现两个上限：

- 无台词片段只能靠上下文猜测，边界和标题容易不贴视频；
- 标题容易被字幕结构带偏，缺少画面里的动作、地点、人物状态信息。

因此新增一个高成本 multimodal 版本，用完整视频帧采样 + 字幕时间线一起交给 MLLM，观察上限效果。

## 2. 第一版目标

新增独立 pipeline，不替换 text-only baseline：

```text
video.mp4 + video.transcription.json + video_metadata
  -> 1 秒 1 帧抽帧
  -> 降分辨率
  -> 字幕时间线 + 帧时间戳 + 帧图片
  -> MLLM
  -> story_chapters.json
```

输出仍沿用 `story_chapters.json` 结构，方便现有 viewer 直接切换 `--chapter-output-root` 查看。

## 3. 输入与采样

输入：

- `video_path`
- `transcription_path`
- `video_metadata.duration_seconds`

采样：

- 按 `0, 1, 2, ... floor(duration)` 每秒抽一帧；
- 不设置 `max_frames`；
- 抽帧后降低分辨率，第一版沿用现有 `pipelines.utils.extract_frames_at_timestamps()` 的降采样能力；
- MLLM 输出的内部章节边界必须来自 `FRAME_TIMESTAMPS`；
- 最后一章 `end_time = VIDEO_DURATION_SECONDS` 是唯一允许不等于帧时间戳的边界。

## 4. Prompt 规则

MLLM 可以同时使用：

- 视频帧：判断无台词片段、场景、动作、表情、转场、地点变化；
- 字幕时间线：判断剧情语义、台词关系和切分点；
- 视频时长：保证覆盖完整时间线。

章节必须：

- 覆盖 `0.0 -> VIDEO_DURATION_SECONDS`；
- 连续、无重叠、无 gap；
- 左闭右开 `[start_time, end_time)`；
- title 是自然短剧剧情导航标签，不是“开局设定/冲突升级”等分析词。

## 5. 文件边界

新增：

- `pipelines/story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation_multimodal_batch.py`
- `tests/test_story_chapter_generation_multimodal.py`
- `tests/test_story_chapter_generation_multimodal_script.py`

不修改 text-only pipeline 的行为。

## 6. 非目标

第一版不做：

- 帧数量优化；
- 视觉摘要预处理；
- 自动重试和分段调用；
- 合并 text-only 与 multimodal 输出；
- 前端编辑反馈。

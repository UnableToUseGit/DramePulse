# 当前实现状态

本文档只记录仓库当前已经落地的实现，不替代架构设计文档。

## 1. 已实现链路

当前算法侧保留四条已确定实现的算法线：

```text
pipelines/expression_trigger/
pipelines/story_chapter/
pipelines/inner_voice_danmaku/
pipelines/danmaku_exploration.py
```

旧 `highlight_candidate_generation`、`highlight_recognition` 和 `interaction_plan_generation` pipeline 已废弃并移除。Expression Trigger workflow 当前写出干净资产 `expression_triggers.json` 和调试产物 `expression_triggers.debug.json`；旧 baseline 脚本仍可能写出 `highlight_recognition.json`，评估和复核工具会优先读取新资产并兼容旧文件名。

## 2. 当前脚本入口

- `scripts/transcribe_video.py`
- `scripts/run_expression_trigger_workflow_batch.py`
- `scripts/run_expression_trigger_mllm_baseline_batch.py`
- `scripts/run_expression_trigger_text_baseline_batch.py`
- `scripts/story_chapter/run_text.py`
- `scripts/story_chapter/run_text_batch.py`
- `scripts/story_chapter/run_mllm.py`
- `scripts/story_chapter/run_mllm_batch.py`
- `scripts/story_chapter/run_subtitle_scene_aligned.py`
- `scripts/story_chapter/run_subtitle_scene_aligned_batch.py`
- `scripts/story_chapter/evaluate_workflow.py`
- `scripts/run_inner_voice_danmaku_generation.py`
- `scripts/run_danmaku_exploration.py`

## 2.1 当前应用入口

- `apps/player-demo/`
- `apps/story-chapter-viewer/`

`apps/player-demo/` 是 React Native + Expo 移动端播放器 Demo。当前版本只包含单个竖屏短剧播放页，使用本地 fixture 展示普通弹幕、中间弹幕投票条、比例反馈、共鸣弹幕、debug 面板和端内事件统计。

`apps/story-chapter-viewer/` 是 Story Chapter 本地检查与标注工具，由 `scripts/story_chapter/viewer_server.py` 提供数据和视频服务。当前版本支持查看算法生成的 `story_chapters.json`，并标注人工 gold chapter boundary。人工标注只记录内部边界点，不手工填写 `start_time` 和 `end_time`；保存时服务端自动按 `[0.0, boundaries..., duration]` 生成 non-gap、non-overlap 的 gold chapters。`boundaries[].ending_chapter_summary` 表示以该 boundary 为 `end_time` 的章节摘要；最后一个以视频 `duration` 为 `end_time` 的章节摘要单独保存在 `final_chapter_summary`，不通过接近 `duration` 的伪 boundary 表达。导出的 `chapters[].summary` 使用这些摘要，boundary 本身不再保存 `reason`。

Story Chapter subtitle-scene aligned workflow 当前会写出两类产物：

- `story_chapters.json`：干净最终产物，用于上传或被前端/评估脚本消费，只包含 `video_id`、`series_id`、`created_at` 和 `story_chapters`。每个章节只包含 `chapter_id`、`start_time`、`end_time`、`title`、`summary`、`reason`。
- `story_chapters.debug.json`：完整诊断产物，保留字幕、场景、稀疏帧抽取信息、边界复核任务、MLLM raw response、warnings 等调试字段。`apps/story-chapter-viewer/` 会继续读取 `story_chapters.json` 中的章节；如果同目录存在 debug 产物，则从 debug 产物读取 warnings 用于本地复核。

Expression Trigger workflow 当前会写出两类产物：

- `expression_triggers.json`：干净最终产物，用于上传或被播放器/评估脚本消费，只包含 `video_id`、`series_id`、`created_at` 和 `expression_triggers`。每个触发点只包含 `trigger_id`、`start_time`、`end_time`、`cue_time`、`ui_trigger_time`、`expression_type`、`interaction_mode`、`intensity`、`confidence`、`summary`、`reason`。
- `expression_triggers.debug.json`：完整诊断产物，保留输入路径、LLM 调用诊断、候选点、候选复核决策、原始最终触发点、前端 resonance cue 和 legacy `highlight_assets` 兼容转换结果。

Danmaku Exploration 当前从真实弹幕 CSV 生成三类探查产物：

- `episode_profile.json`：每集弹幕规模、时间范围、点赞分布、低质文本数量、高频文本和高赞文本；
- `resonance_windows.json`：按滑动窗口聚合出的弹幕共鸣窗口，包含窗口分数、弹幕数量、去重数量、点赞量、actor charm 命中数、emotion burst 命中数和 top comments；命中 actor charm 的高分窗口优先保留，纯简单情绪或表情堆出来的窗口不会进入该产物；
- `inner_voice_review_candidates.json`：供人工复核的心里话弹幕候选，包含候选文案、source comment、表达意图、共鸣分、心里话适配分和推荐原因。

## 3. 当前样例数据

- `data/case1/ep01.mp4`
- `data/case1/ep01.json`
- `data/case1/ep01.srt`
- `data/case1/ep01.16k-mono.wav`
- `example_output/case1_ep01/highlight_recognition.json`
- `example_output/case1_ep01/interaction_plan_generation.json`

## 4. 当前模型配置

当前算法 pipeline 默认使用火山方舟 `Ark` SDK，也支持通过 `LLM_PROVIDER=openai` 切换 OpenAI 兼容 client。

配置来自 `.env` 或同名环境变量：

- `ARK_BASE_URL`
- `ARK_API_KEY`
- `ARK_MODEL`

默认模型示例：

```text
Doubao-Seed-2.0-pro
```

## 5. 当前约束

- Expression Trigger workflow 使用字幕、全局抽帧、低台词密度视觉窗口和候选复核；
- Story Chapter subtitle-scene aligned workflow 先由 LLM 根据带 `speaker_id` 的字幕和默认每 10 秒一帧的稀疏视频帧生成语义章节草稿，再对每个相邻章节边界单独调用 MLLM。边界搜索范围为两个粗字幕锚点组成区间的前后各 10 秒；MLLM 输入只包含前后章节字幕、搜索范围内字幕和按秒抽取的帧，不暴露 LLM 生成的标题/摘要，也不暴露候选 timestamp 列表，输出必须选择已看到帧的时间戳作为最终边界；
- `thinking` 默认关闭；
- 旧交互方案生成 pipeline 已移除；
- `example_output/` 中保存可直接查看的样例结果；
- `data/case1/` 中保存当前协作样例短剧数据；
- Story Chapter gold 标注默认写入 `data/annotations/story_chapter_gold/<video_id>.annotation.json`；
- 移动端播放器 Demo 当前使用本地 fixture 和端内统计，不接真实后端 API；
- 移动端播放器 Demo 当前通过 Expo Go 预览，尚未配置 EAS Build 安装包；
- Expo CLI 建议使用 Node 22 LTS；Anaconda Node 24 可能触发 `ERR_SOCKET_BAD_PORT`。

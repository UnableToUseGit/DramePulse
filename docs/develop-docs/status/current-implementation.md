# 当前实现状态

本文档只记录仓库当前已经落地的实现，不替代架构设计文档。

## 1. 已实现链路

当前算法侧保留三条已确定实现的算法线：

```text
pipelines/expression_trigger/
pipelines/story_chapter/
pipelines/inner_voice_danmaku/
```

旧 `highlight_candidate_generation`、`highlight_recognition` 和 `interaction_plan_generation` pipeline 已废弃并移除。Expression Trigger 输出仍可写入 `highlight_recognition.json`，这是为了兼容现有评估和复核工具的 artifact 文件名，不代表旧高光识别 pipeline 仍在维护。

## 2. 当前脚本入口

- `scripts/transcribe_video.py`
- `scripts/run_expression_trigger_workflow_batch.py`
- `scripts/run_expression_trigger_mllm_baseline_batch.py`
- `scripts/run_expression_trigger_text_baseline_batch.py`
- `scripts/run_story_chapter_generation.py`
- `scripts/run_story_chapter_generation_batch.py`
- `scripts/run_story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation_multimodal_batch.py`
- `scripts/run_story_chapter_subtitle_scene_aligned.py`
- `scripts/run_story_chapter_subtitle_scene_aligned_batch.py`
- `scripts/evaluate_story_chapter_workflow.py`
- `scripts/run_inner_voice_danmaku_generation.py`

## 2.1 当前应用入口

- `apps/player-demo/`
- `apps/story-chapter-viewer/`

`apps/player-demo/` 是 React Native + Expo 移动端播放器 Demo。当前版本只包含单个竖屏短剧播放页，使用本地 fixture 展示普通弹幕、中间弹幕投票条、比例反馈、共鸣弹幕、debug 面板和端内事件统计。

`apps/story-chapter-viewer/` 是 Story Chapter 本地检查与标注工具，由 `scripts/story_chapter_viewer_server.py` 提供数据和视频服务。当前版本支持查看算法生成的 `story_chapters.json`，并标注人工 gold chapter boundary。人工标注只记录内部边界点，不手工填写 `start_time` 和 `end_time`；保存时服务端自动按 `[0.0, boundaries..., duration]` 生成 non-gap、non-overlap 的 gold chapters。`boundaries[].ending_chapter_summary` 表示以该 boundary 为 `end_time` 的章节摘要；最后一个以视频 `duration` 为 `end_time` 的章节摘要单独保存在 `final_chapter_summary`，不通过接近 `duration` 的伪 boundary 表达。导出的 `chapters[].summary` 使用这些摘要，boundary 本身不再保存 `reason`。

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
- Story Chapter subtitle-scene aligned workflow 先由 LLM 选择章节覆盖的首尾字幕并给出 `reason`，再对齐到镜头边界；相邻台词章节之间的视觉空缺统一交给 MLLM 判断并入前后章节或独立成章；
- `thinking` 默认关闭；
- 旧交互方案生成 pipeline 已移除；
- `example_output/` 中保存可直接查看的样例结果；
- `data/case1/` 中保存当前协作样例短剧数据；
- Story Chapter gold 标注默认写入 `data/annotations/story_chapter_gold/<video_id>.annotation.json`；
- 移动端播放器 Demo 当前使用本地 fixture 和端内统计，不接真实后端 API；
- 移动端播放器 Demo 当前通过 Expo Go 预览，尚未配置 EAS Build 安装包；
- Expo CLI 建议使用 Node 22 LTS；Anaconda Node 24 可能触发 `ERR_SOCKET_BAD_PORT`。

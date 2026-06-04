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
- `scripts/run_inner_voice_danmaku_generation.py`

## 2.1 当前应用入口

- `apps/player-demo/`

该目录是 React Native + Expo 移动端播放器 Demo。当前版本只包含单个竖屏短剧播放页，使用本地 fixture 展示普通弹幕、中间弹幕投票条、比例反馈、共鸣弹幕、debug 面板和端内事件统计。

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
- `thinking` 默认关闭；
- 旧交互方案生成 pipeline 已移除；
- `example_output/` 中保存可直接查看的样例结果；
- `data/case1/` 中保存当前协作样例短剧数据；
- 移动端播放器 Demo 当前使用本地 fixture 和端内统计，不接真实后端 API；
- 移动端播放器 Demo 当前通过 Expo Go 预览，尚未配置 EAS Build 安装包；
- Expo CLI 建议使用 Node 22 LTS；Anaconda Node 24 可能触发 `ERR_SOCKET_BAD_PORT`。

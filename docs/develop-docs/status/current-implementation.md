# 当前实现状态

本文档只记录仓库当前已经落地的实现，不替代架构设计文档。

## 1. 已实现链路

当前已经打通的最小链路为：

```text
data/case1/ep01.mp4
data/case1/ep01.srt
data/case1/ep01.json
  ↓
scripts/run_highlight_recognition.py
  ↓
output/case1_ep01/highlight_recognition.json
  ↓
scripts/run_interaction_plan_generation.py
  ↓
output/case1_ep01/interaction_plan_generation.json
```

## 2. 当前脚本入口

- `scripts/transcribe_video.py`
- `scripts/run_highlight_recognition.py`
- `scripts/run_interaction_plan_generation.py`

## 3. 当前样例数据

- `data/case1/ep01.mp4`
- `data/case1/ep01.json`
- `data/case1/ep01.srt`
- `data/case1/ep01.16k-mono.wav`
- `example_output/case1_ep01/highlight_recognition.json`
- `example_output/case1_ep01/interaction_plan_generation.json`

## 4. 当前模型配置

高光识别和交互方案生成都使用火山方舟 `Ark` SDK。

配置来自 `.env` 或同名环境变量：

- `ARK_BASE_URL`
- `ARK_API_KEY`
- `ARK_MODEL`

默认模型示例：

```text
Doubao-Seed-2.0-pro
```

## 5. 当前约束

- 高光识别使用多图理解，不走视频 URL；
- `thinking` 默认关闭；
- 交互方案生成当前只支持 `danmaku_poll`；
- `example_output/` 中保存可直接查看的样例结果；
- `data/case1/` 中保存当前协作样例短剧数据。

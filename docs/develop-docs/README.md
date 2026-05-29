# 开发文档索引

本目录存放 DramePulse 的工程设计、模块说明、接口约定、数据流程和实现状态文档。产品背景与比赛展示材料不放在这里，分别见 `docs/product-spec/`、`docs/competition-instructions/` 和 `docs/presentation/`。

## 顶层设计

- `architecture-design.md`：三层架构、核心数据对象和模块边界。适合在改动跨层契约前阅读。

## 模块设计

- `module-designs/highlight-recognition.md`：高光点识别 pipeline 的输入、输出、流程和边界。
- `module-designs/interaction-plan-generation.md`：互动方案生成 pipeline 的输入、输出、流程和边界。
- `module-designs/mobile-player-demo.md`：移动端播放器 Demo 的体验层设计。

## API 与后端

- `api/interface-requirements.md`：移动端播放器需要的后端 API 形态。
- `backend/lightrag-story-qa-adapter.md`：Story Q&A 的 LightRAG 可选后端接入说明。

## 数据与标注

- `data/dataset-construction.md`：短剧样例数据、弹幕采集和人工标注流程。
- `data/video-manifest-design.md`：视频 manifest 结构和入库映射。

## 播放器专项

- `player/player-interaction-lab-design.md`：播放器 Interaction Lab 的开发工具设计。
- `player/player-vertical-swipe-requirements.md`：播放器上下滑切集需求。

## 当前状态

- `status/current-implementation.md`：当前已经落地的实现状态。

## 维护规则

- 新增模块设计放入 `module-designs/`。
- 新增 API 契约或前后端接口说明放入 `api/`。
- 新增数据集、采集、标注、manifest 相关说明放入 `data/`。
- 新增播放器专项实验、需求或实现说明放入 `player/`。
- 新增当前状态记录放入 `status/`。
- 不要把临时执行计划、个人草稿或工具生成过程记录放入 `docs/develop-docs/`。

# AGENTS.md

本文件是给在 DramePulse 仓库中工作的代码代理看的仓库级说明。

## 项目背景

DramePulse 是一个字节跳动比赛项目，方向是短剧观看场景下的即时互动。

产品目标是构建一套面向移动端短剧消费场景的“即时互动激发系统”：

- 识别短剧中容易激发用户表达欲的剧情高光点；
- 在用户观看过程中触发低摩擦互动；
- 让用户不打断播放也能表达情绪或观点；
- 采集用户行为，并反哺高光点评分与互动策略。

不要把本项目理解成泛视频 App、社交评论系统、弹幕系统或推荐系统。项目核心是下面这条闭环：

```text
内容/字幕 -> 高光资产 -> 互动方案 -> 播放器内互动 -> 用户事件 -> 统计结果 -> 策略更新
```

## 当前仓库状态

当前仓库已经从文档优先阶段进入 MVP 实现阶段。仓库中已有移动端播放器 Demo、FastAPI 后端、算法 pipeline、人工标注工具、共享数据契约、样例数据和测试。

重要文件：

- `README.md`：项目入口说明、目录结构和前端/后端/算法 Quick Start。
- `packages/contracts/`：跨模块共享数据契约，包括核心 JSON Schema 和示例数据。
- `docs/product-spec/prd.md`：产品背景、用户痛点、MVP 目标、交互设想。
- `docs/product-spec/交互设计.png`：弹幕投票交互草图。
- `docs/develop-docs/README.md`：开发文档索引。
- `docs/develop-docs/architecture-design.md`：架构设计、模块契约、数据对象、MVP 边界。
- `docs/develop-docs/status/current-implementation.md`：当前实现状态说明。
- `docs/develop-docs/api/interface-requirements.md`：移动端播放器需要的后端接口说明。
- `docs/develop-docs/data/dataset-construction.md`：数据集构建、弹幕采集和标注流程说明。
- `docs/develop-docs/module-designs/`：高光识别、互动方案生成、播放器 Demo 等模块设计。
- `docs/competition-instructions/`：比赛题目资料。
- `apps/player-demo/`：React Native + Expo 移动端播放器 Demo。
- `apps/annotation-tool/`：高光点人工标注前端。
- `services/api/`：FastAPI 后端服务。
- `pipelines/` 与 `scripts/`：高光点识别、互动方案生成、转写、数据处理和调试脚本。

开始任何实现前，先阅读 PRD、架构设计和当前实现状态；如果改动涉及某个模块，还要阅读对应的 module design 或接口文档。

## 目录约定

代码和资料按以下目录边界放置：

- `apps/`：面向用户或评委的应用入口，例如短剧播放前端、互动 Demo、后台 Dashboard。
- `services/`：在线服务代码，例如后端 API、用户行为接收、互动方案下发、统计查询、策略更新。
- `pipelines/`：离线处理流程，例如字幕解析、高光点识别、互动方案生成、验证集评估。
- `packages/`：跨模块共享代码和定义，例如 JSON Schema、TypeScript 类型、事件类型、高光类型。
- `data/`：少量开发和演示数据，例如样例字幕、元数据、人工标注、高光识别结果、互动方案 JSON。开发数据应先从 Hugging Face 数据集 `TheThreeKeyboardeers/ShortDramas` 或团队当前数据源下载，再移动或整理到该目录下；大体积视频不要直接提交到 GitHub。
- `scripts/`：开发和调试工具脚本，例如下载数据、初始化数据库、导入结果、生成 demo 数据、一键启动服务。
- `docs/`：项目文档，例如 PRD、系统设计、模块契约、API 说明、数据格式说明、实验评估、答辩方案。

## 架构边界

遵循现有三层架构：

- 体验层：播放器渲染、即时互动 UI、用户行为采集；
- 业务层：高光点识别、互动方案生成、行为统计、策略更新；
- 数据层：内容、高光、互动方案、事件、统计和策略日志的持久化。

三个跨层核心对象：

- `Highlight Asset`：回答“哪里值得互动”；
- `Interaction Plan`：回答“如何与用户互动”；
- `User Event`：回答“用户如何反馈”。

保持模块职责清晰：

- 前端不负责判断高光质量，也不负责生成策略；
- 高光识别模块不负责 UI 渲染，也不负责采集用户事件；
- 数据层不承载业务解释逻辑；
- 策略更新模块不直接操作播放器。

## 实现建议

继续写代码时，要刻意保持小而完整，优先补齐端到端链路和比赛答辩可展示能力。

建议边界：

- 前端：移动端优先的短剧播放器 Demo，当前使用 React Native + Expo；
- 主交互：优先实现弹幕投票，选项控制在 2 到 3 个；
- 后端：提供视频、弹幕、互动方案、用户事件、播放事件、互动结果和 Story Q&A 相关 API；
- 数据：本地模式直接读取 `dramepulse.sqlite`，云端已有部署 API `http://39.96.219.88:8000`；数据契约要清楚；
- 高光识别：MVP 可以采用“字幕 + 多图理解 + LLM 结构化抽取 + 人工校验”；
- 策略更新：先用简单规则，不要一开始引入复杂机器学习。

常用入口：

- 后端本地启动：`uvicorn services.api.main:app --host 127.0.0.1 --port 8000`；
- 后端云端地址：`http://39.96.219.88:8000`；
- 前端启动：进入 `apps/player-demo/` 后运行 `npm start`；
- 前端连接云端：`EXPO_PUBLIC_API_BASE_URL=http://39.96.219.88:8000 npm start`；
- 高光识别：`python scripts/run_highlight_recognition.py case1_ep01`；
- 互动方案生成：`python scripts/run_interaction_plan_generation.py case1_ep01`；
- 标注工具：`python scripts/serve_annotation_tool.py --port 8770`，访问 `http://127.0.0.1:8770/apps/annotation-tool/`。

MVP 阶段避免主动扩展：

- 完整用户账号系统；
- 大规模推荐系统；
- 原生移动端 App；
- 实时流处理；
- 支付、电商或广告系统；
- 复杂个性化用户画像。

## 数据契约要求

优先沿用并扩展 `docs/develop-docs/architecture-design.md` 中定义的数据结构。

核心契约已放在 `packages/contracts/`：

- `packages/contracts/schemas/highlight-asset.schema.json`
- `packages/contracts/schemas/interaction-plan.schema.json`
- `packages/contracts/schemas/user-event.schema.json`

示例数据放在 `packages/contracts/examples/`。

预期实体包括：

- video metadata；
- subtitle segments；
- highlight assets；
- interaction plans；
- interaction options；
- user events；
- highlight stats；
- option stats；
- strategy logs。

修改数据契约时，必须同步更新架构文档或新增设计说明，写清楚：

- 改了什么；
- 为什么改；
- 影响哪些模块；
- 现有 demo 数据是否需要迁移。

## 文档规则

这个项目会被评审项目思路、呈现效果和工程完整性。文档必须保持可读、准确、可答辩。

新增或修改行为时：

- 同步更新相关产品文档或架构文档；
- 优先写具体例子，不要只写抽象结论；
- 新增 API 或实体时给出数据样例；
- 明确标注假设；
- 不要留下没有责任人、原因和下一步动作的 TODO。

产品向文档优先使用中文。技术标识符、API 字段名、数据对象名保留英文。

## GitHub 协作原则

`main` 分支只放确认无误、已经合并的稳定内容。不要直接在 `main` 上开发具体功能，除非用户在当前对话中明确要求在 `main` 上做改动。

每个具体功能、实验、修复或文档草稿都应在独立分支中完成。推荐分支命名：

- `feature/player-demo`
- `feature/api-events`
- `feature/highlight-pipeline`
- `docs/dataset-construction`
- `fix/<short-description>`

合并到 `main` 前，应完成自查和必要验证，并通过 Pull Request 合并。代码代理不得在未获明确指令时直接把实验性或未验证内容推到 `main`。

## 前端体验原则

用户正在移动端观看短剧。互动必须快速、低摩擦，并尽量不打断剧情。

遵循这些原则：

- 不阻断主要观看体验；
- 尽量避免遮挡人物、字幕和剧情关键区域；
- 优先使用点击交互，再考虑长按、滑动或连点；
- 用户操作后要立即反馈；
- 互动要像剧情高光的一部分，而不是一个突兀问卷；
- 第一版 demo 要有足够好的视觉呈现，能支撑比赛展示。

当前 PRD 下，弹幕投票是 MVP 的主交互形式。

## 验证要求

声明工作完成前：

- 如果已有代码，运行相关 build、test、lint 或 smoke check；
- 如果只改文档，读回变更后的 Markdown，检查路径和链接；
- 如果某些检查无法运行，说明原因。

不要声称测试通过，除非本轮实际运行过对应测试命令。

## 协作注意事项

- 仓库里可能包含用户或队友写的草稿，不要擅自大段重写；
- 保持现有项目方向，不要把范围扩成无关平台；
- 优先做小而可审查的改动；
- 引入新框架或重大目录结构前，先和用户确认；
- 未经明确要求，不要删除原始文档、参考资料或设计素材。

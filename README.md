# DramePulse

DramePulse 是一个面向短剧观看场景的即时互动激发系统。项目目标是在短剧播放过程中识别剧情高光点，触发低摩擦互动，让用户在不中断观看的情况下完成情绪或观点表达，并将用户反馈回流到高光点评分与互动策略中。

## 目录结构说明

```text
apps/
```

存放面向用户的应用入口，例如短剧播放前端、互动 Demo 页面、后台 Dashboard 等。它负责把系统能力呈现给用户或评委，是体验层的主要实现位置。

```text
services/
```

存放在线服务代码，例如后端 API、用户行为接收、互动方案下发、统计查询、策略更新等。它通常以常驻服务形式运行，负责响应前端请求，并连接业务逻辑与数据存储。

```text
pipelines/
```

存放离线处理流程，例如字幕解析、高光点识别、互动方案生成、验证集评估等。它主要用于把原始短剧视频和字幕加工成系统可用的高光资产与互动数据。

```text
packages/
```

存放多个模块共享的代码和定义，例如核心数据结构、JSON Schema、TypeScript 类型、事件类型枚举、高光类型枚举等。它用于统一前端、后端和算法 pipeline 之间的数据契约，避免各模块格式不一致。

```text
data/
```

存放少量开发与演示所需的数据文件，例如样例字幕、元数据、人工标注、高光识别结果、互动方案 JSON 等。大体积视频数据不建议直接提交到 GitHub，可通过 Hugging Face private dataset 管理。

开发和演示数据应先从 Hugging Face 数据集 `TheThreeKeyboardeers/ShortDramas` 下载，再移动或整理到 `data/` 目录下。不要直接把大体积视频文件提交到 GitHub。

```text
scripts/
```

存放开发和调试过程中常用的小工具脚本，例如下载数据、初始化数据库、导入高光结果、生成 demo 数据、一键启动服务等。它们不属于主业务逻辑，但能提升开发效率。

```text
docs/
```

存放项目文档，例如 PRD、系统设计、模块契约、API 说明、数据格式说明、实验评估、答辩方案等。它用于沉淀项目设计思路，方便团队协作和后续汇报。

## 共享数据契约

系统设计中的三个核心数据结构已经提前放在 `packages/contracts/`：

- `Highlight Asset`：高光资产，描述哪里值得触发互动；
- `Interaction Plan`：互动方案，描述前端如何触发和渲染互动；
- `User Event`：用户行为事件，描述用户在播放和互动过程中的反馈。

对应 JSON Schema 位于 `packages/contracts/schemas/`，示例数据位于 `packages/contracts/examples/`。

## GitHub 协作原则

`main` 分支只放确认无误、已经合并的稳定内容。不要直接在 `main` 上开发具体功能。

每位成员应基于 `main` 创建自己的功能分支，例如：

```text
feature/player-demo
feature/api-events
feature/highlight-pipeline
docs/dataset-construction
```

具体功能、实验脚本、文档草稿都应先在独立分支中完成，经过自查和必要验证后，再通过 Pull Request 合并到 `main`。

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

存放少量开发与演示所需的数据文件，例如样例视频、样例字幕、弹幕元数据、人工标注、高光识别结果、互动方案 JSON 等。

当前仓库保留了一个轻量协作样例 `data/case1/`，用于端到端调试。更大规模数据仍建议通过 Hugging Face 数据集 `TheThreeKeyboardeers/ShortDramas` 管理。

```text
scripts/
```

存放开发和调试过程中常用的小工具脚本，例如下载数据、初始化数据库、导入高光结果、生成 demo 数据、一键启动服务等。它们不属于主业务逻辑，但能提升开发效率。

```text
docs/
```

存放项目文档，例如 PRD、系统设计、模块契约、API 说明、数据格式说明、实验评估、答辩方案等。它用于沉淀项目设计思路，方便团队协作和后续汇报。

```text
third_party/
```

存放 DramePulse 集成但不作为主产品代码维护的外部源码。当前内置的 `third_party/video-analyzer` 是后台“视频解析/剧情资料生成”流程使用的离线视频理解引擎，负责生成 `transcript.json`、`frame_analyses.jsonl`、`analysis.json` 和 `fusion_result.md`。复现方式见 `docs/develop-docs/video-analyzer-integration.md`。

## 共享数据契约

系统设计中的三个核心数据结构已经提前放在 `packages/contracts/`：

- `Highlight Asset`：高光资产，描述哪里值得触发互动；
- `Interaction Plan`：互动方案，描述前端如何触发和渲染互动；
- `User Event`：用户行为事件，描述用户在播放和互动过程中的反馈。

对应 JSON Schema 位于 `packages/contracts/schemas/`，示例数据位于 `packages/contracts/examples/`。

## 本地运行算法链路

当前已经提供一个可运行样例：

```text
data/case1/ep01.mp4
data/case1/ep01.srt
data/case1/ep01.json
```

复制 `.env.example` 为 `.env`，填写火山方舟配置：

```env
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_API_KEY=你的 API Key
ARK_MODEL=Doubao-Seed-2.0-pro
```

运行高光点识别：

```bash
python scripts/run_highlight_recognition.py case1_ep01
```

运行交互方案生成：

```bash
python scripts/run_interaction_plan_generation.py case1_ep01
```

默认输出目录为：

```text
output/case1_ep01/highlight_recognition.json
output/case1_ep01/interaction_plan_generation.json
```

仓库中也保留了一份可查看的样例输出：

```text
example_output/case1_ep01/
```

更多模块设计说明见：

- `docs/develop-docs/module-designs/highlight-recognition.md`
- `docs/develop-docs/module-designs/interaction-plan-generation.md`
- `docs/develop-docs/module-designs/mobile-player-demo.md`
- `docs/develop-docs/status/current-implementation.md`

## 本地运行移动端播放器 Demo

当前移动端 Demo 位于：

```text
apps/player-demo/
```

它是一个 React Native + Expo App，包含竖屏短剧播放页、弹幕互动和播放中观看助手入口。Demo 从后端读取视频列表、视频流和弹幕，在 iOS 和 Android 上可通过 Expo Go 扫码体验。

安装依赖并启动：

```bash
cd apps/player-demo
nvm use
npm install
npm start
```

启动后使用手机上的 Expo Go 扫描终端中的二维码。默认 API 地址为同源 `/`；本地 Expo Go 调试时可通过环境变量指定后端：

```bash
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm start
```

播放页右侧“助手”按钮可打开“观看助手”面板，前端调用 `POST /api/watch-assistant/act`。助手可以复用剧情 RAG 回答问题，也可以返回 `seek`、`next_episode`、`pause`、`resume` 等播放器动作，由前端执行并上报事件。如果后端设置 `STORY_QA_BACKEND=lightrag`，剧情问答工具会通过 LightRAG working directory 回答剧情问题。

观看助手也支持语音输入。移动端使用 `expo-audio` 录音并上传到 `POST /api/watch-assistant/transcribe`，后端完成 ASR 转写后，前端会把转写文本继续提交给 `POST /api/watch-assistant/act`。语音输入只是助手输入方式升级，不替代高光识别、互动方案或用户事件契约。默认 `WATCH_ASSISTANT_ASR_BACKEND=mock` 便于本地调试；真实演示可设置 `WATCH_ASSISTANT_ASR_BACKEND=openai_compatible`、`OPENAI_API_KEY`、`OPENAI_API_BASE` 和 `WATCH_ASSISTANT_ASR_MODEL`。

如果本机使用 Anaconda 自带的 Node 24，Expo CLI 可能在端口探测阶段报 `ERR_SOCKET_BAD_PORT`。建议在该目录使用 `.nvmrc` 指定的 Node 22 LTS 后再启动。

## 本地运行后台只读看板

后台管理看板位于：

```text
apps/admin-dashboard/
```

它是一个 Vite + React + TypeScript Web 应用，读取 `GET /api/admin/dashboard`，展示视频、互动方案、投票分布、用户事件统计和最近事件流。当前版本只读，不提供登录、编辑、删除或批量操作。

当前后台也提供轻量内容管理入口，可以创建短剧、上传剧封面、上传每集视频。上传资源会通过后端写入 OSS 或本地模拟 OSS，并同步 upsert 到现有 `videos` 表。第一版只管理剧名、封面和视频，弹幕、高光、字幕、知识图谱和互动方案上传暂未接入。

内容管理使用的 OSS key 规范：

```text
dramas/{series_id}/name.txt
dramas/{series_id}/cover.jpg
dramas/{series_id}/episodes/ep01/video.mp4
```

先启动本地 API：

```bash
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

再启动后台看板：

```bash
cd apps/admin-dashboard
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5174
```

开发模式下 Vite 会把 `/api` 请求代理到 `http://127.0.0.1:8000`。

内容管理接口：

```text
POST /api/admin/series
POST /api/admin/series/{series_id}/cover
POST /api/admin/series/{series_id}/episodes
```

## 本地运行后端 API

当前后端 API 位于：

```text
services/api/
```

### 本地优先调试模式

后端默认使用本地模式，协作者 clone 仓库后可以直接使用同一份调试数据，不依赖远程 RDS MySQL 或 OSS。

根目录提交的共享调试数据：

```text
demo_video.mp4
dramepulse.sqlite
```

默认本地配置：

```env
DRAMEPULSE_MODE=local
SQLITE_PATH=dramepulse.sqlite
LOCAL_OSS_ROOT=.
LOCAL_OSS_BUCKET=local
```

初始化或刷新本地 SQLite：

```bash
python -m services.api.scripts.init_local_dev
```

本地启动 API：

```bash
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

本地检查：

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/videos
GET http://127.0.0.1:8000/api/videos/demo_ep01/stream
```

如需使用阿里云 RDS MySQL 和 OSS，将 `.env` 中 `DRAMEPULSE_MODE` 改为 `cloud`，并填写 MySQL/OSS 配置。两种模式的 API 路径保持一致。

它是一个 FastAPI 服务，第一版提供 OSS 视频代理播放和播放行为事件记录。视频元数据保存在 MySQL，视频文件本体保存在 OSS，播放器通过后端 `/stream` 接口播放，避免 OSS 默认域名触发下载行为。

安装依赖后，先初始化数据库并从 OSS 导入视频元数据：

```bash
python -m services.api.scripts.init_db
python -m services.api.scripts.import_oss_videos
```

启动服务：

```bash
uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

核心接口：

```text
GET  /api/health
GET  /api/videos
GET  /api/videos/{video_id}
GET  /api/videos/{video_id}/stream
POST /api/playback-events
POST /api/watch-assistant/act
```

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
## Optional story Q&A RAG

`/api/story-qa/*` is an optional plot Q&A capability for answering questions within the viewer's current playback progress. The default backend uses Chroma, LlamaIndex, and an OpenAI-compatible API. A LightRAG backend can also load a prebuilt working directory for graph-based plot Q&A. This feature does not replace highlight recognition, interaction plan generation, or strategy updates.

Endpoints:

```text
POST /api/story-qa/ask
POST /api/story-qa/ingest
GET  /api/story-qa/collections
```

Real RAG calls require these `.env` values:

```env
STORY_QA_BACKEND=chroma
OPENAI_API_KEY=
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_DIR=data/chroma
CHROMA_COLLECTION=dramepulse_story_qa
SIMILARITY_TOP_K=8
```

To use the optional LightRAG backend, install the chapter-aware LightRAG package locally, build each drama knowledge graph offline with per-episode `chapter_ids`, and copy each whole working directory into `data/story_qa/{series_id}/lightrag`. Then set:

```env
STORY_QA_BACKEND=lightrag
LIGHTRAG_WORKING_ROOT=data/story_qa
LIGHTRAG_QUERY_MODE=hybrid
LIGHTRAG_ENABLE_RERANK=false
LIGHTRAG_EMBEDDING_MODEL=text-embedding-3-small
LIGHTRAG_EMBEDDING_DIM=1536
LIGHTRAG_EMBEDDING_API_BASE=https://api.openai.com/v1
LIGHTRAG_EMBEDDING_API_KEY=
LIGHTRAG_EMBEDDING_SEND_DIM=false
```

The player Q&A panel uses the same `/api/story-qa/ask` endpoint. For LightRAG, DramePulse selects `LIGHTRAG_WORKING_ROOT/{series_id}/lightrag` and maps `current_episode` to `QueryParam.current_chapter_id`, so cross-drama isolation depends on the directory layout and episode-level spoiler filtering depends on `chapter_id` metadata. `current_time` is not used by LightRAG filtering in this version.

## Watch assistant

`/api/watch-assistant/act` is a lightweight orchestration layer on top of Story Q&A. It accepts the viewer's current playback context and returns display text plus structured actions for the frontend to execute.

Request shape:

```json
{
  "message": "快进到高光",
  "series_id": "demo",
  "video_id": "demo_ep01",
  "current_episode": 1,
  "current_time": 20.0,
  "duration": 90.0,
  "available_tools": ["story_qa", "seek", "seek_relative", "next_episode", "pause", "resume"]
}
```

Response shape:

```json
{
  "reply": "已准备跳到 0:42。",
  "actions": [{ "type": "seek", "target_time": 42.0, "reason": "按助手指令跳转" }],
  "tool_calls": [{ "tool": "seek", "arguments": { "target": "highlight" }, "status": "ok", "result": { "target_time": 42.0 } }],
  "sources": []
}
```

The backend never controls the player directly. Playback actions are executed by `apps/player-demo`, and assistant-triggered playback behavior is reported through `/api/events` with `extra.source = "watch_assistant"`.

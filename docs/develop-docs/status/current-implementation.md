# 当前实现状态

本文档记录仓库当前已经落地的实现状态。它只描述事实，不替代 `docs/develop-docs/architecture-design.md`、模块设计文档或 README Quick Start。

## 1. 总体状态

当前仓库已经包含四条可运行或可展示的主线：

```text
FastAPI 后端
  -> 视频、弹幕、互动方案、事件、Story Q&A API

React Native + Expo 播放器
  -> 后端视频列表/视频流/弹幕
  -> 竖滑播放 Feed
  -> Interaction Lab
  -> Story Q&A 面板

算法 pipeline
  -> 高光点识别
  -> 互动方案生成

标注工具
  -> 浏览器内播放视频、查看弹幕时间轴、导出人工高光标注
```

## 2. 后端 API

代码入口：

```text
services/api/
services/api/main.py
```

本地启动：

```bash
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

云端 API：

```text
http://39.96.219.88:8000
```

当前后端已包含这些路由模块：

- `health`：健康检查；
- `videos`：视频列表、视频详情、视频流、视频弹幕读取；
- `danmaku`：用户弹幕写入；
- `interactions`：互动方案读取、互动结果读取；
- `events`：统一用户事件上报；
- `playback_events`：播放事件上报；
- `story_qa`：剧情问答检索与问答接口。

核心接口包括：

```text
GET  /api/health
GET  /api/videos
GET  /api/videos/{video_id}
GET  /api/videos/{video_id}/stream
GET  /api/videos/{video_id}/danmaku
POST /api/videos/{video_id}/danmaku
GET  /api/videos/{video_id}/interaction-plans
GET  /api/interactions/{interaction_id}/results
POST /api/events
POST /api/playback-events
POST /api/story-qa/ask
POST /api/story-qa/ingest
GET  /api/story-qa/collections
```

运行模式：

- 本地模式默认读取根目录 `dramepulse.sqlite`；
- 云端部署已经可通过 `http://39.96.219.88:8000` 访问；
- 本地 API 也可以通过 `.env` 切换到 cloud 模式，连接云端 MySQL/OSS 配置。

## 3. 移动端播放器 Demo

代码入口：

```text
apps/player-demo/
apps/player-demo/src/screens/PlayerScreen.tsx
apps/player-demo/src/components/PlayerPage.tsx
```

启动方式：

```bash
cd apps/player-demo
npm install
npm start
```

当前已实现：

- React Native + Expo 移动端播放器；
- 从后端 `GET /api/videos` 获取视频列表；
- 使用后端 `stream_url` 播放视频；
- 使用后端 `danmaku_url` 获取弹幕，并在端内做移动端采样和调度展示；
- 竖滑 Feed 播放多集/多视频；
- 播放、暂停、seek、长按倍速、播放结束切下一集；
- 右侧操作栏、顶部/底部播放器 Chrome；
- Story Q&A 面板，调用 `POST /api/story-qa/ask`；
- Interaction Lab，用本地固定 example 对比 `poll_bar`、`danmaku_poll`、`emoji_hold` 等互动呈现方式。

当前边界：

- 播放器已经接入后端视频和弹幕；
- 播放器当前的 Interaction Lab 仍是前端本地互动形态实验，不等同于完整的服务端 `Interaction Plan` 自动触发链路；
- 播放器当前未配置 EAS Build 安装包，主要通过 Expo Go 预览；
- Expo CLI 建议使用 `apps/player-demo/.nvmrc` 指定的 Node 版本；Anaconda Node 24 可能触发 `ERR_SOCKET_BAD_PORT`。

## 4. 算法 Pipeline

脚本入口：

```text
scripts/transcribe_video.py
scripts/run_highlight_recognition.py
scripts/run_interaction_plan_generation.py
```

核心实现：

```text
pipelines/highlight_recognition.py
pipelines/interaction_plan_generation.py
pipelines/client.py
```

样例链路：

```text
data/case1/ep01.mp4
data/case1/ep01.srt
data/case1/ep01.json
  ↓
python scripts/run_highlight_recognition.py case1_ep01
  ↓
output/case1_ep01/highlight_recognition.json
  ↓
python scripts/run_interaction_plan_generation.py case1_ep01
  ↓
output/case1_ep01/interaction_plan_generation.json
```

当前能力：

- 高光点识别使用字幕、多图理解和 LLM 结构化输出；
- 互动方案生成消费 `Highlight Asset`、字幕窗口、关键帧和弹幕上下文；
- 当前互动方案生成以 `danmaku_poll` 为主；
- 生成失败时有 fallback 模板；
- 剧情导航章节生成支持 text-only baseline 和 multimodal 高成本版本；
- 剧情导航验证 viewer 可用于播放视频、对照 scene 边界和 story chapter 边界；
- 样例输出保存在 `example_output/case1_ep01/`。

剧情导航章节生成入口：

```text
scripts/run_story_chapter_generation.py
scripts/run_story_chapter_generation_batch.py
scripts/run_story_chapter_generation_multimodal.py
scripts/run_story_chapter_generation_multimodal_batch.py
scripts/story_chapter_viewer_server.py
```

剧情导航章节生成的当前实现与验证结论见：

- `docs/develop-docs/module-designs/story-chapter-generation.md`

运行前提：

- `.env` 中配置 `ARK_BASE_URL`、`ARK_API_KEY`、`ARK_MODEL`；
- `data/case1/ep01.srt` 和 `data/case1/ep01.json` 已在仓库中；
- `data/case1/ep01.mp4` 如不存在，需要从本地样例视频或外部数据源补齐。

## 5. 人工标注工具

代码入口：

```text
apps/annotation-tool/
scripts/serve_annotation_tool.py
```

启动方式：

```bash
python scripts/serve_annotation_tool.py --port 8770
```

访问：

```text
http://127.0.0.1:8770/apps/annotation-tool/
```

当前能力：

- 从后端 API 获取视频列表和视频详情；
- 使用视频对象中的 `stream_url` 播放视频；
- 读取并展示弹幕时间轴；
- 支持记录高光 `start_time`、`end_time`、`emotion`、`reason`；
- 支持导出人工标注 JSON；
- 可通过 `api_base_url` 指向本地后端或云端后端。

## 6. 共享数据契约

共享契约位于：

```text
packages/contracts/
```

当前核心 schema：

- `packages/contracts/schemas/highlight-asset.schema.json`
- `packages/contracts/schemas/interaction-plan.schema.json`
- `packages/contracts/schemas/user-event.schema.json`

示例数据位于：

```text
packages/contracts/examples/
```

修改数据契约时，需要同步更新架构设计、接口说明或模块设计中相关字段说明。

## 7. 已知未完全打通的部分

- 播放器已接入后端视频和弹幕，但服务端 `Interaction Plan` 自动触发与完整事件回传链路仍需进一步对齐前端实现；
- 策略更新模块仍以设计和规则说明为主，尚未形成完整可演示闭环；
- Story Q&A 的 Chroma/OpenAI 或 LightRAG 后端需要额外环境变量和索引数据；
- 算法链路依赖火山方舟 API Key 和本地视频文件；
- `docs/develop-docs/api/interface-requirements.md` 和实际后端 schema 仍需要继续保持同步。

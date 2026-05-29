# DramePulse

DramePulse 是一个面向移动端短剧观看场景的即时互动激发系统。

项目目标不是做泛视频 App、评论系统或推荐系统，而是验证一条面向比赛展示的闭环：

```text
内容/字幕/弹幕
  -> 高光资产 Highlight Asset
  -> 互动方案 Interaction Plan
  -> 播放器内低摩擦互动
  -> 用户事件 User Event
  -> 统计结果与策略更新
```

当前仓库已经包含三个主要部分：

- `apps/player-demo/`：React Native + Expo 移动端播放器 Demo；
- `services/api/`：FastAPI 后端，提供视频、弹幕、互动方案、用户事件和 Story Q&A API；
- `pipelines/` 与 `scripts/`：高光点识别、互动方案生成、转写、数据导入等离线流程。

共享数据契约位于 `packages/contracts/`，核心对象包括 `Highlight Asset`、`Interaction Plan` 和 `User Event`。

## 目录结构

```text
apps/
  player-demo/          # 移动端播放器 Demo
  annotation-tool/      # 高光点人工标注工具

services/
  api/                  # FastAPI 后端服务

pipelines/
  highlight_recognition.py
  interaction_plan_generation.py

scripts/
  run_highlight_recognition.py
  run_interaction_plan_generation.py
  transcribe_video.py

packages/
  contracts/            # JSON Schema 和示例数据

data/
  case1/                # 小规模样例数据，视频文件可按需本地补齐

docs/
  product-spec/         # 产品文档
  develop-docs/         # 架构、模块、接口和状态文档
```

## 准备 Python 环境

后端和算法脚本共用 Python 依赖。建议使用 Python 3.11 及以上版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env.example` 默认使用本地后端模式：

```env
DRAMEPULSE_MODE=local
SQLITE_PATH=dramepulse.sqlite
LOCAL_OSS_ROOT=.
LOCAL_OSS_BUCKET=local
```

## 后端 Quick Start

后端位于：

```text
services/api/
```

后端有两种访问方式。

方式一是使用已经部署好的云端 API：

```text
http://39.96.219.88:8000
```

可以直接检查：

```text
GET http://39.96.219.88:8000/api/health
GET http://39.96.219.88:8000/api/videos
```

方式二是在本地启动 API。本地模式会直接读取根目录下的 `dramepulse.sqlite`。当前不需要手动运行初始化脚本，确认 `.env` 保持默认本地配置后直接启动 API 即可。

启动 API：

```bash
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

真机调试前端时，需要让手机访问到开发机上的后端，可以改用：

```bash
uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

常用检查接口：

```text
GET  http://127.0.0.1:8000/api/health
GET  http://127.0.0.1:8000/api/videos
GET  http://127.0.0.1:8000/api/videos/demo_ep01
GET  http://127.0.0.1:8000/api/videos/demo_ep01/stream
GET  http://127.0.0.1:8000/api/videos/demo_ep01/danmaku
GET  http://127.0.0.1:8000/api/videos/demo_ep01/interaction-plans
```

当前后端还提供：

```text
POST /api/events
POST /api/playback-events
POST /api/videos/{video_id}/danmaku
GET  /api/interactions/{interaction_id}/results
POST /api/story-qa/ask
POST /api/story-qa/ingest
GET  /api/story-qa/collections
```

本地启动的 API 也可以通过 `.env` 切换到云端 MySQL/OSS 模式：将 `DRAMEPULSE_MODE` 改为 `cloud`，并补齐 MySQL、OSS、CDN 相关配置。

## 前端 Quick Start

播放器 Demo 位于：

```text
apps/player-demo/
```

它是一个 React Native + Expo App，当前能力包括：

- 竖屏短剧播放；
- 后端视频列表与视频流加载；
- 普通弹幕展示；
- 竖向滑动切集；
- Interaction Lab 互动形态实验；
- 右侧剧情问答入口，调用 `POST /api/story-qa/ask`。

启动前需要确认前端可以访问后端 API。可以使用本地 API，也可以直接使用已经部署好的云端 API。

```bash
cd apps/player-demo
nvm use
npm install
npm start
```

启动后用 Expo Go 扫描终端二维码。

前端默认会尝试从 Expo Metro 地址推断后端主机。真机无法访问后端时，可以显式指定后端地址。

使用云端 API：

```bash
EXPO_PUBLIC_API_BASE_URL=http://39.96.219.88:8000 npm start
```

使用本地开发机 API：

```bash
EXPO_PUBLIC_API_BASE_URL=http://<your-lan-ip>:8000 npm start
```

Windows PowerShell：

```powershell
$env:EXPO_PUBLIC_API_BASE_URL="http://<your-lan-ip>:8000"
npm start
```

如果本机使用 Anaconda 自带的 Node 24，Expo CLI 可能在端口探测阶段报 `ERR_SOCKET_BAD_PORT`。建议使用 `apps/player-demo/.nvmrc` 指定的 Node 版本。

前端常用检查：

```bash
npm run typecheck
npm test
```

## 算法 Quick Start

算法链路包含两步：

```text
视频 + 字幕 + 弹幕
  -> 高光点识别
  -> 互动方案生成
```

样例输入默认使用 `video_id = case1_ep01`，脚本会读取：

```text
data/case1/ep01.mp4
data/case1/ep01.srt
data/case1/ep01.json
```

如果 `data/case1/ep01.mp4` 不存在，可以先复制播放器 Demo 内置视频：

```bash
cp apps/player-demo/assets/video/ep01.mp4 data/case1/ep01.mp4
```

在 `.env` 中填写火山方舟配置：

```env
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_API_KEY=你的 API Key
ARK_MODEL=Doubao-Seed-2.0-pro
```

运行高光点识别：

```bash
python scripts/run_highlight_recognition.py case1_ep01
```

运行互动方案生成：

```bash
python scripts/run_interaction_plan_generation.py case1_ep01
```

默认输出到：

```text
output/case1_ep01/highlight_recognition.json
output/case1_ep01/interaction_plan_generation.json
```

仓库中保留了一份可直接查看的样例输出：

```text
example_output/case1_ep01/
```

### 人工标注工具

算法链路还配套一个本地高光点标注前端，用于人工查看视频、弹幕时间轴并导出高光标注 JSON。

启动标注工具静态服务：

```bash
python scripts/serve_annotation_tool.py --port 8770
```

访问：

```text
http://127.0.0.1:8770/apps/annotation-tool/
```

标注工具默认同源请求后端 API。如果后端使用本地 `8000` 端口或云端部署地址，可以通过 `api_base_url` 指定：

```text
http://127.0.0.1:8770/apps/annotation-tool/?api_base_url=http://127.0.0.1:8000
http://127.0.0.1:8770/apps/annotation-tool/?api_base_url=http://39.96.219.88:8000
```

更多算法设计说明：

- `docs/develop-docs/module-designs/highlight-recognition.md`
- `docs/develop-docs/module-designs/interaction-plan-generation.md`

## 关键文档

- `docs/product-spec/prd.md`：产品背景、用户痛点、MVP 目标和交互设想；
- `docs/develop-docs/README.md`：开发文档索引；
- `docs/develop-docs/architecture-design.md`：三层架构、模块边界和核心数据对象；
- `docs/develop-docs/status/current-implementation.md`：当前实现状态；
- `docs/develop-docs/api/interface-requirements.md`：前端接口需求；
- `docs/develop-docs/module-designs/mobile-player-demo.md`：移动端播放器模块设计；
- `packages/contracts/README.md`：跨模块数据契约说明。

## 验证建议

只改后端或算法时：

```bash
pytest
```

只改播放器前端时：

```bash
cd apps/player-demo
npm run typecheck
npm test
```

只改文档时，至少读回变更后的 Markdown，确认路径、命令和文件名仍与仓库一致。

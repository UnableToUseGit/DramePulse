# DramePulse

DramePulse 是一个面向移动端短剧观看场景的即时互动系统。其提供贴合场景特点、符合用户习惯的表达交互入口，让用户以不打断、低摩擦、0 门槛的方式完成情绪表达。同时，项目实现了一套视频数据基建，把原始短剧视频解析为章节、节拍、caption、互动触发点等结构化数据。这些数据可以被播放器、互动组件和 Agent 能力复用，避免后续开发直接消费笨重的视频文件。此外，在工程侧，DramePulse 提供了完整的前后端实现，使互动能力能够稳定运行在真实移动端播放链路中，并支持后续继续扩展剧集、互动形态和 Agent 能力。

## 核心亮点

- **贴合短剧观看习惯的轻量互动**：在剧情高光处提供情绪按钮、心里话弹幕等表达入口，用户无需打字、无需跳出播放页，就能完成即时表达并获得反馈。
- **从视频到结构化内容资产**：通过转写、章节生成、剧情节拍生成和互动触发点识别，将短剧视频转为播放器、互动组件和 Agent 能力都能复用的数据资产。
- **真实移动端播放链路中的互动呈现**：播放器支持短剧列表、竖屏 Feed、上下滑切集、播放控制、章节进度条、storyboard 预览和互动资产触发，让互动能力嵌入实际观看流程。
- **Drama Copilot 陪看助手**：支持剧情问答、跳转高光、切换剧集、暂停/继续等能力，让用户可以在观看过程中自然地探索剧情。
- **剧情拓展与商业化探索**：支持在剧集 Feed 中插入角色商品广告页，由服务端广告 slot 下发，前端按剧集位置自动编排和播放。
- **稳定可扩展的前后端系统**：FastAPI 后端提供视频、剧集、互动资产、用户事件、播放事件、Story Q&A、广告 slot 和后台看板等 API；前端侧配合首屏预热、请求编排、播放资产缓存和 Feed 预加载，支撑更稳定的演示体验。
- **完整的生产与复核工具链**：包含人工标注工具、算法复核工具、剧情章节查看器和后台内容管理入口，方便持续迭代高光资产、剧情章节和互动形态。

这些能力可以支撑短剧高光互动 Demo、剧情导航、陪看助手、互动广告探索，以及后续面向 Agent 的短剧内容应用开发。

## 快速启动

### 1. 准备 Python 环境

建议使用 Python 3.11 及以上版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

默认 `.env.example` 使用本地模式，读取仓库根目录下的 `dramepulse.sqlite`。

### 2. 启动后端 API

本地启动：

```bash
uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

真机调试时，如果手机需要访问开发机后端，可以改为：

```bash
uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

检查接口：

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/videos
```

也可以直接使用已经部署好的云端 API：

```text
http://39.96.219.88:8000
```

### 3. 启动移动端播放器

```bash
cd apps/player-demo
nvm use
npm install
npm start
```

启动后使用 Expo Go 扫描终端二维码。

连接云端 API：

```bash
EXPO_PUBLIC_API_BASE_URL=http://39.96.219.88:8000 npm start
```

连接本地局域网 API：

```bash
EXPO_PUBLIC_API_BASE_URL=http://<your-lan-ip>:8000 npm start
```

如果 Expo CLI 在端口探测时报 `ERR_SOCKET_BAD_PORT`，请确认当前 Node 版本使用的是 `apps/player-demo/.nvmrc` 指定版本。

### 4. 可选：启动后台看板

先启动后端 API，然后运行：

```bash
cd apps/admin-dashboard
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5174
```

### 5. 可选：运行算法链路

运行 Expression Trigger 高光触发点识别：

```bash
python scripts/expression_trigger/run_workflow_batch.py --video-id case1_ep01 --force
```

运行 Story Chapter 剧情章节生成：

```bash
python scripts/story_chapter/run_text.py case1_ep01
```

算法链路需要在 `.env` 中配置模型服务，例如火山方舟或 OpenAI 兼容接口。

### 6. 可选：启动人工标注工具

```bash
python scripts/serve_annotation_tool.py --port 8770
```

访问：

```text
http://127.0.0.1:8770/apps/annotation-tool/
```

## 目录结构

```text
apps/
  player-demo/              # Expo 移动端播放器 Demo
  admin-dashboard/          # 后台看板和内容管理入口
  annotation-tool/          # 人工高光标注工具
  algorithm-review-tool/    # 算法结果复核工具
  story-chapter-viewer/     # 剧情章节查看器

services/
  api/                      # FastAPI 后端服务

pipelines/
  expression_trigger/       # 高光触发点识别
  story_chapter/            # 剧情章节生成
  plot_beat/                # 剧情节拍生成
  inner_voice_danmaku/      # 心里话弹幕生成

scripts/
  expression_trigger/       # 高光识别脚本入口
  story_chapter/            # 剧情章节脚本入口
  plot_beat/                # 剧情节拍脚本入口
  inner_voice_danmaku/      # 心里话弹幕脚本入口
  tools/                    # 数据、媒体和标注辅助脚本

packages/
  contracts/                # Highlight Asset / Interaction Plan / User Event 契约

docs/
  product-spec/             # 产品说明
  develop-docs/             # 架构、接口、模块设计和实现状态
  competition-instructions/ # 赛题说明
```

## 更多文档

- [产品 PRD](docs/product-spec/prd.md)
- [架构设计](docs/develop-docs/architecture-design.md)
- [当前实现状态](docs/develop-docs/status/current-implementation.md)
- [前端接口需求](docs/develop-docs/api/interface-requirements.md)
- [移动端播放器模块设计](docs/develop-docs/module-designs/mobile-player-demo.md)
- [共享数据契约](packages/contracts/README.md)

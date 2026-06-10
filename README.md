# DramePulse

DramePulse 是一个面向移动端短剧APP的即时互动系统。其提供贴合场景特点、符合用户习惯的表达交互入口，让用户以不打断、低摩擦、0 门槛的方式完成情绪表达。同时，项目实现了一套视频数据基建，把原始短剧视频解析为章节、节拍、caption、互动触发点等结构化数据。这些数据可以被播放器、互动组件和 Agent 能力复用，避免后续开发直接消费笨重的视频文件。此外，在工程侧，DramePulse 提供了完整的前后端实现，使互动能力能够稳定运行在真实移动端播放链路中，并支持后续继续扩展剧集、互动形态和 Agent 能力。

## 核心亮点

- **分层表达的即时互动设计**：DramePulse 设计了情绪按钮和心里话弹幕两种互动方式。情绪按钮承接最直接的情绪释放（“爽、甜、笑、哭”），从用户熟悉的右侧交互区域中轻轻滑入，触发后的视觉反馈干净利索；心里话弹幕则面向更高层级的语义表达，系统预生成弹幕内容，从弹幕按钮旁边轻轻冒出，用户只需轻推即可发送。两者都复用短剧用户熟悉的表达形式，在不打断播放的前提下降低表达门槛。
- **视频结构化 Pipeline**：系统结合音频转录，镜头切分和多模态大模型等技术，搭建视频数据处理流水线。从视频解析出 “剧情章节”、“剧情节拍”、“高光触发点”、“剧情描述” 等资产并以结构化 JSON/API 的形式下发给播放器和 Agent，使短剧内容从“视频文件”变成可检索、可调度、可交互的数据资产。
- **基于角色移情的 AIGC 互动广告页**：DramePulse 没有把 AIGC 生硬用于剧情分支，而是结合剧情语境和角色形象生成广告内容，编排进剧集播放流。广告页保留短剧播放体验，同时提供 CTA 按钮，用户点击后可打开商品详情页完成进一步了解。它利用观众对剧中角色的移情，让广告成为更自然，观众更喜闻乐见的内容转化入口。
- **短剧智能陪看助手**：DramePulse 引入更具前瞻性的交互入口 —— Agentic Interface，让用户不只是和视频内容交互，也能和 Agent 交互。助手基于当前剧集、播放进度和结构化剧情数据，支持剧情问答、跳转高光、切换剧集、暂停/继续等能力。
- **面向真实体验的前后端系统**：DramePulse 前端实现了首页、剧场列表页和剧集播放页等基础页面，包含完整播放器能力，并围绕移动端短剧播放流实现互动触发、章节进度条、storyboard 预览、广告页和陪看助手入口。同时，前端实现了有效的视频流管控，包括首屏资产预热、请求编排、播放资产缓存和相邻页预加载等机制。后端完成云端部署，提供 CDN + HLS 的视频传输能力，并围绕前端所需要的资产提供完整 API。项目还配套后台管理页面，用于内容管理和数据查看。
- **面向算法迭代的标注与复核工具链**：DramePulse 配套建设了人工标注工具、算法复核工具和剧情章节查看器，并沉淀了一批人工标注验证集，让视频结构化 pipeline 的产物可以被查看、标注、对比和复核，支撑后续持续迭代。


## 快速启动

运行项目分三步：

1. **准备环境**：安装 Python 依赖和前端 npm 依赖。
2. **启动后端**：本地开发时启动 FastAPI；如果只想体验 App，可以跳过本地后端，直接使用已部署的公网服务。
3. **启动前端**：进入 `apps/player-demo/` 启动 Expo，并用 Expo Go 打开移动端 Demo。

### 1. 准备环境

后端和算法脚本建议使用 Python 3.11 及以上版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

默认 `.env.example` 使用本地模式，读取仓库根目录下的 `dramepulse.sqlite`。

播放器前端位于 `apps/player-demo/`：

```bash
cd apps/player-demo
nvm use
npm install
```

### 2. 启动后端 API

如果只想体验 App，可以跳过本节，直接使用已部署的公网服务：

```text
http://39.96.219.88:8000
```

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

### 3. 启动移动端播放器

```bash
cd apps/player-demo
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

### 4. 打包移动端 App

播放器 Demo 已配置 EAS Build。比赛演示最快路径是先打 Android APK，安装到安卓真机即可使用云端 API。

注意：下面命令必须在 `apps/player-demo/` 这个 Expo 项目目录里执行，不要在仓库根目录直接运行；否则会找不到 `.nvmrc`、`package-lock.json` 或 EAS 项目配置。

```bash
cd apps/player-demo
nvm use
npm ci
npx eas-cli@latest login
npx eas-cli@latest build -p android --profile preview
```

首次 EAS 构建可能会提示登录、创建或关联 Expo 项目，按 CLI 提示完成即可。构建完成后，EAS 会输出一个 `.apk` 下载链接；也可以在项目页面查看历史构建：

```text
https://expo.dev/accounts/minghaoqin/projects/dramepulse-player-demo
```

`preview`、`simulator` 和 `production` 构建配置默认连接云端 API：

```text
http://39.96.219.88:8000
```

iOS 真机包需要 Apple Developer 凭证，可使用 production 构建；如果只需要在 iOS Simulator 验收，可先构建 simulator profile：

```bash
npx eas-cli@latest build -p ios --profile simulator
```

## 致谢

本项目在视频分析与镜头切分能力上参考或使用了以下开源项目：

- [video-analyzer](https://github.com/byjlw/video-analyzer)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)

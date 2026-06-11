# DramePulse

DramePulse 是一个面向移动端短剧APP的即时互动系统。其提供贴合场景特点、符合用户习惯的表达交互入口，让用户以不打断、低摩擦、0 门槛的方式完成情绪表达。同时，项目实现了一套视频数据基建，把原始短剧视频解析为章节、节拍、caption、互动触发点等结构化数据。这些数据可以被播放器、互动组件和 Agent 能力复用，避免后续开发直接消费笨重的视频文件。此外，在工程侧，DramePulse 提供了完整的前后端实现，使互动能力能够稳定运行在真实移动端播放链路中，并支持后续继续扩展剧集、互动形态和 Agent 能力。

## 核心亮点

- **不打断的即时表达**：通过共鸣按钮和心里话弹幕，让用户在熟悉的右侧交互区和弹幕入口完成表达。前者承接“爽、甜、笑、哭”等即时情绪，后者承接更完整的观点表达。
- **视频结构化轻资产**：结合音频转录、镜头切分和多模态大模型，将短剧解析为剧情章节、剧情节拍、caption、互动触发点等结构化资产，供播放器、互动组件和 Agent 复用。
- **AIGC 互动广告页**：基于剧情语境和角色形象生成广告内容，并将其编排进剧集播放流。广告页支持 CTA 和商品详情页，让内容延展自然承接商业转化。
- **短剧智能陪看助手**：基于当前剧集、播放进度和结构化剧情数据，支持剧情问答、跳转高光、切换剧集、暂停/继续等 Agentic Interface 能力。
- **完整移动端播放体验**：前端实现首页、剧场列表页和剧集播放页，包含播放器、弹幕、章节进度条、storyboard 预览、广告页和陪看助手入口，并提供首屏预热、请求编排、缓存和相邻页预加载。
- **可持续迭代的工具链**：后端完成云端部署、CDN + HLS 视频传输、完整 API 和后台管理页面；同时配套人工标注工具、算法复核工具和剧情章节查看器，支撑后续扩展与复核。


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

### 5. 统一 Pipeline CLI

仓库提供统一的本地 pipeline 命令入口，用于开发、调试和答辩演示。该入口会列出可运行算法能力，并把参数转发给对应 pipeline runner：

```bash
python -m dramepulse_cli.main --help
python -m dramepulse_cli.main --version
python -m dramepulse_cli --help
python -m dramepulse_cli.main pipelines list
python -m dramepulse_cli.main pipelines info highlight-commerce
```

安装为 package 后也可以直接使用 `dramepulse` 命令：

```bash
pip install -e .
dramepulse pipelines run highlight-commerce \
  --asset data/role-commerce-v2/highlight_commerce_case1.json \
  --output-root output/role-commerce-v2
```

当前 CLI registry 包含 `expression-trigger`、`story-chapter`、`inner-voice-danmaku` 和 `highlight-commerce` 四条主线。

## 致谢

本项目在视频分析与镜头切分能力上参考或使用了以下开源项目：

- [video-analyzer](https://github.com/byjlw/video-analyzer)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)

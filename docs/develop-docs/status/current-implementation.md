# 当前实现状态

本文档记录仓库当前已经落地的实现状态。它只描述事实，不替代 `docs/develop-docs/architecture-design.md`、模块设计文档或 README Quick Start。

## 1. 总体状态

当前仓库已经包含四条可运行或可展示的主线：

```text
FastAPI 后端
  -> 视频、弹幕、互动方案、事件、Story Q&A API

React Native + Expo 播放器
  -> 后端视频列表/视频流
  -> 竖滑播放 Feed
  -> Interaction Lab
  -> Story Q&A 面板

算法 pipeline
  -> 高光点识别
  -> 互动方案生成
  -> 高光带货 v2 视频生成

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
GET  /api/videos/{video_id}/interaction-assets
GET  /api/videos/{video_id}/story-chapters
GET  /api/series/{series_id}/ad-slots
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
- 弹幕层仍保留端内调度和本地互动反馈渲染能力，但当前云端联调版本暂不请求后端 `danmaku_url`，默认返回空弹幕，避免全量弹幕响应拖慢首屏和播放页切换；
- 竖滑 Feed 播放多集/多视频；
- 播放、暂停、seek、长按倍速、播放结束切下一集；
- Home Feed 在开发模式下提供播放观测面板和 `[HomeFeedPlayback]` 结构化终端日志，可查看页面挂载、预加载、播放权、播放器状态、真实播放状态和首帧耗时；
- Home Feed 播放编排已拆分页面角色，包括 `active`、`preload` 和 `parked`，预加载页可在不拥有播放权时准备恢复进度；
- Home Feed 根据页面角色拆分渲染负载：`active` 页渲染完整互动播放器，`preload` 页保留同一个静音 `VideoStage` 做资源准备但跳过重 UI，`parked` 页只保留占位；
- Home Feed 手动竖滑时使用 `onScrollEndDrag` 预测最终目标页并提前切换播放权，`onMomentumScrollEnd` 只做最终校准；
- Home Feed 拖动期间会缓冲播放进度上报，等滚动结束后再同步到 App 顶层播放位置状态，减少滑动中的重渲染；
- Home Feed 远程剧集视频启用 `expo-video` source caching 和保守前向 buffer 配置，`source_load` 观测会带上 `cacheEnabled` 与 `bufferedPosition`；
- App 启动页会先加载首页 Feed、剧场列表、首集 storyboard、story chapters 和 interaction assets，并预取首集全量 storyboard sheet；数据准备完成后先挂载首页播放器，继续显示启动遮罩直到首页第一个视频满足播放 ready 状态机（首帧已渲染、播放器进入 playing、播放时间已前进），避免启动页消失后只露出静止首帧；
- 播放页轻量资产加载已接入 `GET /api/videos/{video_id}/story-chapters` 和 `GET /api/videos/{video_id}/interaction-assets`；story chapters 会写入播放资产缓存并驱动进度条章节刻度，`emotional_button` 会映射为 `action-rail-resonance`，`inner_voice_danmaku` 会映射为 `inner-voice-danmaku`；
- 互动资产只在播放时间自然推进进入 `trigger_time` 到 `expire_time` 窗口时触发；用户拖动进度条或 seek 落入触发窗口时会跳过该互动并标记完成，避免 seek 后突然弹出交互组件；
- 播放 Debug 面板开启时，播放器进度条会额外显示 interaction asset 的 `trigger_time` marker，用于检查互动资产加载和触发时间；用户态默认不显示；
- 剧集 Feed 的角色商品广告已接入 `GET /api/series/{series_id}/ad-slots`，前端按 slot 的 `after_episode_no` 将广告插入对应集之后；广告视频优先播放后端 `stream_url`，没有远程流时才 fallback 到端内 `assets/video/ads.mp4`；
- 播放器进度条的 storyboard 预览层保持常驻，并用隐藏的 storyboard sheet warm layer 预挂载当前视频 sheet，避免用户开始拖动时才创建预览图片组件；
- Home Feed 播放观测在开发模式下会批量写入本地 `logs/home-feed-playback.log`，前提是前端连接本地 FastAPI；
- Home Feed 播放观测已补充 `resume_position_initialized`、`seek_requested` 和 `seek_applied`，用于验证恢复进度是否先于播放执行；
- 右侧操作栏、顶部/底部播放器 Chrome；
- Story Q&A 面板，调用 `POST /api/story-qa/ask`；
- Interaction Lab，用本地固定 example 对比 `poll_bar`、`danmaku_poll`、`emoji_hold`、`emotion_aura`、`inner_voice_danmaku` 等互动呈现方式。

当前边界：

- 播放器已经接入后端视频流、首页 Feed、剧场列表、首集 storyboard、story chapters 和 interaction assets；远程弹幕读取暂时关闭，后续需要拆分弹幕分页或按时间窗口加载后再恢复；
- `/api/videos/{video_id}/playback-assets` 暂不作为前端预热来源，避免全量弹幕响应重新进入启动链路；
- Home Feed 播放观测只保留本次运行的内存事件，不持久化、不上报后端，也不属于业务 `User Event`；
- 播放观测当前不覆盖 Series Feed、广告页、弹幕和互动组件渲染成本；
- 剧集广告当前只负责读取服务端 slot、插入 Feed 和播放广告视频，还未接入广告曝光、点击、转化等事件上报；
- 播放器当前的 Interaction Lab 仍是前端本地互动形态实验，不等同于完整的服务端 `Interaction Plan` 自动触发链路；
- 播放器已配置 EAS Build，`preview` profile 可产出 Android APK 演示包，`simulator` profile 可产出 iOS Simulator 包，`production` profile 可用于正式 iOS/Android 构建；各 profile 默认连接云端 API；
- Expo CLI 建议使用 `apps/player-demo/.nvmrc` 指定的 Node 版本；Anaconda Node 24 可能触发 `ERR_SOCKET_BAD_PORT`。
- TanStack Query 可以作为后续数据请求治理增强项评估；当前阶段先沿用项目已有 domain loader、启动预热器和播放资产缓存，避免在性能问题尚未收敛前引入新的全局缓存语义。

## 4. 算法 Pipeline

当前算法侧保留三条主要实现线：

```text
pipelines/expression_trigger/
pipelines/story_chapter/
pipelines/inner_voice_danmaku/
pipelines/highlight_commerce/generation.py
pipelines/highlight_commerce/script_generation.py
pipelines/highlight_commerce/v2_pipeline.py
```

旧 `highlight_candidate_generation`、`highlight_recognition` 和 `interaction_plan_generation` pipeline 已废弃并移除。Expression Trigger workflow 当前写出干净资产 `expression_triggers.json` 和调试产物 `expression_triggers.debug.json`；旧 baseline 脚本仍可能写出 `highlight_recognition.json`，评估和复核工具会优先读取新资产并兼容旧文件名。

当前脚本入口：

```text
dramepulse_cli/main.py
scripts/transcribe_video.py
scripts/expression_trigger/run_workflow_batch.py
scripts/expression_trigger/run_mllm_baseline_batch.py
scripts/expression_trigger/run_text_baseline_batch.py
scripts/expression_trigger/run_interaction_plan_batch.py
scripts/story_chapter/run_text.py
scripts/story_chapter/run_text_batch.py
scripts/story_chapter/run_mllm.py
scripts/story_chapter/run_mllm_batch.py
scripts/story_chapter/run_subtitle_scene_aligned.py
scripts/story_chapter/run_subtitle_scene_aligned_batch.py
scripts/story_chapter/evaluate_workflow.py
scripts/story_chapter/viewer_server.py
scripts/inner_voice_danmaku/run_batch.py
scripts/inner_voice_danmaku/semantic_clustering.py
scripts/inner_voice_danmaku/select_candidates.py
scripts/inner_voice_danmaku/build_interaction_plan.py
scripts/highlight_commerce/run_cartoon_assets.py
scripts/highlight_commerce/run_seedance_render.py
scripts/highlight_commerce/run_v2_pipeline.py
```

当前能力：

- 统一 Pipeline CLI 通过 `python -m dramepulse_cli.main` 或安装后的 `dramepulse` 命令提供 `--version`、ANSI banner 帮助页、`pipelines list/info/run`，用于本地开发和答辩演示；
- Expression Trigger workflow 使用字幕、全局抽帧、低台词密度视觉窗口和候选复核，输出前端可消费的表达触发资产；
- Story Chapter subtitle-scene aligned workflow 先由 LLM 根据带 `speaker_id` 的字幕和稀疏视频帧生成语义章节草稿，再对相邻章节边界单独调用 MLLM 复核；
- Inner Voice Danmaku pipeline 支持从真实弹幕 CSV 做语义聚类、候选筛选，并生成心里话弹幕互动方案；
- 高光带货 v2 pipeline 支持从高光图、角色图、产品图和角色参考音频生成广告脚本、卡通参考图，并调用 Seedance 生成 12 秒竖屏带货视频；
- 剧情导航验证 viewer 位于 `apps/story-chapter-viewer/`，由 `scripts/story_chapter/viewer_server.py` 提供数据和视频服务，支持查看算法生成章节并标注人工 gold chapter boundary；
- 算法复核工具位于 `apps/algorithm-review-tool/`，用于对照 Expression Trigger 结果和人工标注；
- 字幕密度工具位于 `apps/subtitle-density-tool/`，用于辅助检查低台词密度视觉窗口。

当前产物约定：

- `story_chapters.json`：干净最终产物，用于上传或被前端/评估脚本消费；
- `story_chapters.debug.json`：完整诊断产物，保留字幕、场景、抽帧、MLLM raw response 和 warnings；
- `expression_triggers.json`：干净最终产物，用于上传或被播放器/评估脚本消费；
- `expression_triggers.debug.json`：完整诊断产物，保留 LLM 调用诊断、候选点、复核决策和 legacy `highlight_assets` 兼容转换结果。
- `highlight_commerce_script.json`：高光带货脚本产物，包含镜头脚本、角色台词、商品引入和生成约束；
- `highlight_commerce_cartoon_asset.json`：Seedream 生成卡通参考图后更新的广告资产；
- `highlight_commerce_v2_result.json`：Seedance 任务状态、输出视频 URL 和本地下载路径。

运行前提：

- `.env` 中配置 `ARK_BASE_URL`、`ARK_API_KEY`、`ARK_MODEL`；也可通过 `LLM_PROVIDER=openai` 切换 OpenAI 兼容 client；
- 高光带货 v2 还需要 `ARK_SEEDREAM_MODEL`、`ARK_SEEDANCE_MODEL` 和对应模型权限；
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

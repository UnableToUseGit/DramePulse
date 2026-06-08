# Video Analyzer 集成说明

## 1. 定位

DramePulse 不直接在主业务代码中实现完整的“视频解析为剧本”算法，而是把 `third_party/video-analyzer` 作为离线视频理解引擎集成进仓库。

两者职责如下：

- `third_party/video-analyzer`：从原始视频中抽取音频转写、关键帧分析，并融合生成剧情说明。
- `DramePulse`：触发解析任务、保存解析结果、在后台展示结果，并把剧情资料接入 Story Q&A 等后续能力。

这样做的原因是让主项目保持“短剧即时互动闭环”的产品边界，同时让 GitHub 仓库包含完整依赖源码，避免只依赖本机路径 `D:\XuPlace\bytedance\project\Vedio\video-analyzer`。

## 2. 代码位置

```text
third_party/video-analyzer/
  video_analyzer/              # 视频解析核心包
  video-analyzer-ui/           # 原项目自带 UI
  video-analyzer-tune/         # Prompt 调优工具
  docs/
  requirements.txt
  setup.py
```

DramePulse 调用入口：

```text
services/api/repositories/admin_analysis.py
```

后台创建解析任务后，DramePulse 会执行：

```text
python -m video_analyzer.cli <video_path> --output <output_dir> ...
```

## 3. 输入输出

输入：

- 已上传并入库的视频文件。

`video-analyzer` 输出：

- `transcript.txt`：转写文本；
- `transcript.json`：带时间戳的转写片段；
- `frame_analyses.jsonl`：逐帧视觉分析；
- `frame_analyses.md`：逐帧视觉分析 Markdown；
- `fusion_result.md`：融合字幕和画面后的剧情说明；
- `analysis.json`：完整结构化结果。

DramePulse 当前主要使用：

- `fusion_result.md`：后台“解析结果”展示；
- `transcript.json`、`frame_analyses.jsonl`、`fusion_result.md`：Story Q&A 入库资料。

## 4. 基础复现路径

基础复现不要求重新跑视频解析模型，适合没有模型 API Key 或本机算力不足的评审环境。

1. 使用仓库中已有的样例数据和预构建 Story Q&A 数据。
2. 启动 DramePulse 后端和前端。
3. 验证播放器、后台、Story Q&A、互动链路可以读取已有数据。

这种路径证明 DramePulse 的产品闭环和服务接口可运行，但不重新生成 `fusion_result.md`。

## 5. 完整复现路径

完整复现会从视频重新生成剧情资料。

### 5.1 安装 video-analyzer

在 DramePulse 仓库根目录执行：

```powershell
python -m venv third_party\video-analyzer\.venv
third_party\video-analyzer\.venv\Scripts\python.exe -m pip install -U pip
third_party\video-analyzer\.venv\Scripts\python.exe -m pip install -e third_party\video-analyzer
```

系统还需要安装 FFmpeg，并保证 `ffmpeg` 可在命令行中调用。

### 5.2 配置环境变量

参考 `.env.example`：

```env
VIDEO_ANALYZER_PYTHON=third_party/video-analyzer/.venv/Scripts/python.exe
VIDEO_ANALYZER_PROJECT=third_party/video-analyzer
VIDEO_ANALYZER_RESULT_ROOT=video-analyzer_result
VIDEO_ANALYZER_CLIENT=openai_api
VIDEO_ANALYZER_API_BASE=https://api.openai.com/v1
VIDEO_ANALYZER_API_KEY=
VIDEO_ANALYZER_MODEL=gpt-4o-mini
VIDEO_ANALYZER_WHISPER_MODEL=small
VIDEO_ANALYZER_MAX_FRAMES=30
```

如果使用 OpenAI-compatible 服务，把 `VIDEO_ANALYZER_API_BASE`、`VIDEO_ANALYZER_API_KEY` 和 `VIDEO_ANALYZER_MODEL` 改成对应供应商配置。

### 5.3 直接验证 video-analyzer

```powershell
third_party\video-analyzer\.venv\Scripts\python.exe -m video_analyzer.cli apps\player-demo\assets\video\ep01.mp4 --output video-analyzer_result\smoke\ep01 --client openai_api --api-key <your-key> --api-url <api-base> --model <vision-model> --max-frames 3
```

成功后应看到：

```text
video-analyzer_result/smoke/ep01/fusion_result.md
video-analyzer_result/smoke/ep01/analysis.json
video-analyzer_result/smoke/ep01/transcript.json
video-analyzer_result/smoke/ep01/frame_analyses.jsonl
```

### 5.4 通过 DramePulse 后台触发

1. 启动 FastAPI 服务。
2. 登录后台管理页。
3. 在内容管理的视频列表中点击“解析”。
4. 后端会创建 `video_analysis_jobs` 记录，并把产物写入 `VIDEO_ANALYZER_RESULT_ROOT/<series_id>/<episode_label>/`。
5. 完成后可在后台查看 `fusion_result.md`。

## 6. GitHub 提交边界

应提交：

- `third_party/video-analyzer` 的源码、文档、依赖清单和 prompt/config；
- DramePulse 的集成代码、配置示例和文档；
- 小体积样例结果。

不应提交：

- `.venv/`；
- `.git/`；
- `output/`、`ui_data/`、`video-analyzer_result/` 等本机生成目录；
- 大体积视频、模型权重、缓存和 API Key。

## 7. 当前限制

- 完整复现需要 FFmpeg、Whisper 相关依赖和可用的视觉大模型服务。
- 模型输出会受模型版本、prompt 和采样帧数量影响，不保证每次完全一致。
- DramePulse 当前只消费解析结果，不在线执行知识图谱抽取；LightRAG working directory 仍应作为离线构建产物提供。

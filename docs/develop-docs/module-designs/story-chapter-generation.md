# 剧情导航章节生成模块设计

## 1. 模块定位

剧情导航章节生成模块负责把一集短剧的完整时间线切分成若干连续章节，用于播放器里的剧情导航。

它解决的问题是：

```text
用户拖动或浏览进度条时，如何快速知道每一段剧情在讲什么
```

它不负责判断高光点是否适合触发互动，也不负责生成弹幕投票、用户反馈或策略更新。和 `Highlight Asset` 相比，`Story Chapter` 更偏导航结构，要求覆盖完整视频时间线；高光点则只覆盖少数适合互动的剧情片段。

当前模块保留两套生成方式：

- text-only 版本：使用转录字幕和视频时长生成章节，成本低，适合批量 baseline；
- multimodal 版本：使用视频帧、转录字幕和视频时长生成章节，成本高，用于探索当前质量上限。

## 2. 当前输入

### 2.1 公共输入

#### `video_id`

视频唯一标识，用于输出目录、章节 ID 和 viewer 索引。

#### `video_metadata.duration_seconds`

视频总时长，单位为秒。章节必须覆盖完整时间线：

```text
0.0 -> VIDEO_DURATION_SECONDS
```

当前脚本仍从 `scene_detection.json` 中读取或推导该字段，但 pipeline 接口已经改为显式接收 `video_metadata` 字典。后续如果有更标准的视频 metadata 文件，可以直接替换脚本侧读取逻辑。

#### `video.transcription.json`

转录字幕文件。模块会从 `raw_response.chunks[].raw_result.transcripts[].sentences[]` 中解析 `Utterance`：

- `utterance_id`
- `start_time`
- `end_time`
- `text`
- `speaker_id`

章节切分的语义依据主要来自这些带时间戳的台词。

### 2.2 text-only 额外输入

#### `scene_detection.json`

当前 text-only 脚本仍要求传入 `scene_detection.json`，用于：

- 读取或推导 `duration_seconds`；
- 在输出中保留 `scenes`，方便 viewer 对照章节和镜头边界。

注意：章节吸附到镜头边界的逻辑已经暂时停用。原因是剧情章节是完整时间线上的语义分段，单独把每个章节的 start/end 吸附到镜头边界容易引入 gap、overlap 或边界语义错位。

### 2.3 multimodal 额外输入

#### `video.mp4`

multimodal 版本会从视频中抽帧，把画面和字幕一起交给 MLLM。

#### 抽帧参数

当前默认策略：

- `frame_interval_seconds = 1.0`
- `max_frames = 120`
- `frame_max_height = 512`

抽帧逻辑是两步：

1. 先按 `frame_interval_seconds` 从 `0.0` 开始采样；
2. 如果采样帧数超过 `max_frames`，再对候选时间戳做均匀下采样。

这个策略来自第一次高成本实验中的实际错误：一秒一帧直接请求完整视频时，容易触发模型服务的 `Request Entity Too Large`。因此当前版本保留高信息量方向，但给请求体加上可控上限。

## 3. 输出格式

两套 pipeline 都输出：

```text
<output_root>/<video_id>/story_chapters.json
```

核心字段：

```json
{
  "video_id": "beipai_xunbao_biji_ep01",
  "video_metadata": {
    "duration_seconds": 297.36
  },
  "story_chapters": [
    {
      "start_time": 0.0,
      "end_time": 18.0,
      "title": "债主堵门",
      "summary": "债主上门逼债，主角试图保护家人。",
      "importance": 0.62,
      "chapter_id": "ch_beipai_xunbao_biji_ep01_001",
      "video_id": "beipai_xunbao_biji_ep01"
    }
  ],
  "warnings": []
}
```

章节约束：

- 第一章 `start_time` 必须为 `0.0`；
- 最后一章 `end_time` 必须为 `VIDEO_DURATION_SECONDS`；
- 相邻章节必须连续，上一章 `end_time` 等于下一章 `start_time`；
- 不允许重叠；
- 章节区间按左闭右开理解：`[start_time, end_time)`；
- 如果某句台词从时间点 `t` 开始，且 `t` 正好是章节边界，则这句台词属于从 `t` 开始的下一章；
- `title` 是自然短剧剧情导航标签，不使用“开局设定”“冲突升级”“高潮收束”等分析型标题；
- `summary` 是基于字幕或画面的简短事实描述。

## 4. text-only 实现状态

实现文件：

- `pipelines/story_chapter_generation.py`
- `scripts/run_story_chapter_generation.py`
- `scripts/run_story_chapter_generation_batch.py`

单集运行示例：

```bash
python scripts/run_story_chapter_generation.py beipai_xunbao_biji_ep01 \
  --transcription /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beipai_xunbao_biji/ep01/video.transcription.json \
  --scene-detection /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beipai_xunbao_biji/ep01/scene_detection.json \
  --output-root output/story_chapter_validation
```

批量运行示例：

```bash
python scripts/run_story_chapter_generation_batch.py \
  --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/story_chapter_validation
```

当前结论：

- 对台词密集的剧情段，text-only 可以给出可用的导航章节；
- 对无台词、弱台词或主要依赖画面动作推进的片段，text-only 只能根据前后字幕猜测，边界和标题容易不准；
- prompt 已经要求覆盖完整时间线，因此无台词开头、结尾或中段也必须被包含到相邻合理章节中；
- title 风格已从技术分析词调整为更像短剧进度条标签的中文短标题，但缺少画面时仍可能和实际视频内容不贴。

## 5. multimodal 实现状态

实现文件：

- `pipelines/story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation_multimodal_batch.py`
- `tests/test_story_chapter_generation_multimodal.py`
- `tests/test_story_chapter_generation_multimodal_script.py`
- `tests/test_story_chapter_generation_multimodal_batch_script.py`

单集运行示例：

```bash
python scripts/run_story_chapter_generation_multimodal.py beipai_xunbao_biji_ep01 \
  --video /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beipai_xunbao_biji/ep01/video.mp4 \
  --transcription /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beipai_xunbao_biji/ep01/video.transcription.json \
  --scene-detection /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm/beipai_xunbao_biji/ep01/scene_detection.json \
  --output-root output/story_chapter_multimodal_validation \
  --frame-interval-seconds 1 \
  --max-frames 120
```

批量运行示例：

```bash
python scripts/run_story_chapter_generation_multimodal_batch.py \
  --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/story_chapter_multimodal_validation \
  --frame-interval-seconds 1 \
  --max-frames 120
```

如果请求体仍然过大，可以先降低最大帧数：

```bash
python scripts/run_story_chapter_generation_multimodal_batch.py \
  --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/story_chapter_multimodal_validation \
  --frame-interval-seconds 1 \
  --max-frames 80
```

或改成更稀疏的初始采样：

```bash
python scripts/run_story_chapter_generation_multimodal_batch.py \
  --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/story_chapter_multimodal_validation \
  --frame-interval-seconds 2 \
  --max-frames 120
```

当前约束：

- 内部章节边界必须来自 `FRAME_TIMESTAMPS_SECONDS`；
- 最后一章 `end_time = VIDEO_DURATION_SECONDS` 是唯一允许不等于帧时间戳的边界；
- MLLM 同时使用帧判断无台词段、动作、表情、地点、转场和可见剧情状态，使用字幕判断台词语义和人物关系。

当前结论：

- multimodal 是当前探索质量上限的版本，不替代 text-only baseline；
- 512 高度的帧在短剧竖屏画面中已经能保留人物关系、动作和主要场景信息，同时显著降低请求体；
- `max_frames` 是必须保留的工程参数，否则长视频或一秒一帧策略会触发请求体过大；
- 后续如果继续优化，可以考虑先做视觉摘要、分段调用或章节候选点二阶段校验，但当前先保留最直接、可解释的高成本方案。

## 6. 验证 viewer

当前本地 viewer 用于人工观察章节切分质量：

- `apps/story-chapter-viewer/`
- `scripts/story_chapter_viewer_server.py`

启动示例：

```bash
python scripts/story_chapter_viewer_server.py \
  --dataset-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --chapter-output-root output/story_chapter_validation \
  --port 8765
```

切换 multimodal 结果时，把 `--chapter-output-root` 改为：

```text
output/story_chapter_multimodal_validation
```

viewer 当前用于：

- 浏览验证集 episode；
- 播放原始视频；
- 对照 scene 边界与 story chapter 边界；
- 点击章节跳转；
- 观察 title、summary 和实际视频内容是否对齐。

这个 viewer 是验证工具，不是最终播放器里的剧情导航入口。

## 7. 与播放器前端的关系

下一步要在 `apps/player-demo` 中增加剧情导航入口，但当前分支的播放器前端不是最新结构。

截至本次对比：

- 当前分支：`feature/story-navigation`；
- `main` 在 `apps/player-demo` 上已有较大重构；
- `HEAD..main -- apps/player-demo` 涉及 32 个文件，约 2022 行新增、647 行删除；
- `main` 新增了 `PlayerActionRail`、`PlayerBottomTabs`、`PlayerMeta`、`PlayerTopBar`、`SpeedSelector`、`StoryQaPanel`、`useDanmakuFeed`、`useInteractionExampleState`、`usePlaybackSpeedControls` 等组件和 hooks；
- 当前分支的 `PlayerChrome`、`PlayerPage` 等仍是旧结构。

因此，剧情导航入口不应该直接接到当前分支的旧播放器结构上。更合理的顺序是：

1. 先把 `main` 合入 `feature/story-navigation`，让播放器组件更新到最新形态；
2. 在新的 `PlayerActionRail`、`PlayerBottomTabs`、`PlayerPage`、`playerApi.ts` 等结构上接入剧情导航；
3. 复用当前 `story_chapters.json` 输出作为前端 fixture 或 API 返回格式；
4. 保留 `apps/story-chapter-viewer` 作为算法结果检查工具，不和正式播放器入口混在一起。

## 8. 当前未解决问题

- `story_chapters.json` 还没有正式放入 `packages/contracts/schemas/`；
- pipeline 只做基础字段解析，尚未强制修复 LLM 返回的 gap、overlap 或末尾不等于 duration 等问题；
- multimodal 版本仍是单次请求，长视频在高帧数下可能受请求体限制；
- viewer 只能人工观察，尚未支持标注反馈写回；
- 播放器前端还未接入剧情导航入口，需要先同步 `main` 的最新组件结构。

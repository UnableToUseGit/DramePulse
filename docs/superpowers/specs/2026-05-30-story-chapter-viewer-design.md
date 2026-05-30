# Story Chapter Viewer 设计记录

## 1. 背景

`Story Chapter` 生成 pipeline 已经能从 `video.transcription.json` 和 `scene_detection.json` 生成章节草稿。当前最需要的是一个只读观察工具，让开发者快速判断章节边界、标题和摘要是否符合视频内容。

第一版工具服务于算法验证闭环，不是面向最终用户的播放器功能。

## 2. 第一版目标

构建一个本地 Web Viewer：

- 读取验证集目录 `/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm`；
- 列出所有短剧和分集；
- 播放选中分集的 `video.mp4`；
- 展示该分集的 `scene_detection.json` 镜头切分；
- 如果存在 `story_chapters.json`，展示章节区间、标题、摘要和重要度；
- 点击章节后跳转到章节开始时间；
- 播放时高亮当前章节。

第一版只读，不写反馈文件，不编辑章节时间，不修改算法输出。

## 3. 数据输入

分集目录约定：

```text
{dataset_root}/{series_slug}/{episode}/
  video.mp4
  scene_detection.json
  story_chapters.json      # 可选，优先读取
```

`story_chapters.json` 优先在分集目录下读取。若不存在，可通过参数指定额外的章节输出根目录，按 `{output_root}/{video_id}/story_chapters.json` 查找。

`video_id` 优先使用 `scene_detection.json` 顶层 `video_id`，缺失时使用 `{series_slug}_{episode}`。

## 4. 界面结构

采用独立桌面 Web 工具：

- 左侧：短剧和分集列表，显示是否已有章节结果；
- 中间：HTML5 video、播放状态、复合时间轴；
- 右侧：章节列表和当前章节详情。

时间轴展示两类信息：

- `scene`：细粒度短刻度，用低对比度细线展示；
- `story_chapter`：较粗的区间条，显示标题，点击跳转。

## 5. 本地服务

新增一个轻量 Python HTTP 服务：

- `GET /api/episodes` 返回验证集分集清单；
- `GET /api/episodes/{episode_id}` 返回单集详情，包括视频 URL、scene 和 chapters；
- `GET /media/{episode_id}/video.mp4` 流式返回本地视频。

服务只读访问验证集，不复制视频，不写回验证集目录。

## 6. 非目标

第一版不做：

- 人工反馈保存；
- 拖动调整章节边界；
- 批量运行 LLM 生成；
- 移动端播放器体验；
- 后端业务 API 集成；
- 用户账号或多人协作。

## 7. 验证方式

- 单元测试覆盖分集发现、章节文件定位、API 数据组装；
- 手动 smoke check：启动 viewer，打开页面，确认能选择分集、播放视频、点击章节跳转。

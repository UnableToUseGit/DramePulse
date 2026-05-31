# 播放器剧情章节时间轴设计记录

## 1. 背景

`Story Chapter` 生成 pipeline 已经能输出一集短剧的连续剧情章节。接下来需要把章节能力接入 `apps/player-demo`，但第一版不做章节列表，也不做额外的剧情导航入口。

本设计直接参考短视频播放器里的拖动预览体验：平时不打扰观看，只在用户操作进度条时把当前位置对应的剧情信息展示出来。

## 2. 第一版目标

第一版只做两件事：

1. 在播放器默认进度条上显示章节分界刻度；
2. 用户拖动进度条时，展示当前位置的视频预览帧、剧情章节标题和时间。

目标效果：

```text
默认观看：
  现有播放器进度条 + 轻量章节刻度

拖动进度条：
  storyboard 预览帧
  当前章节 title
  当前拖动时间 / 视频总时长
  带章节刻度的进度条
```

这个功能的定位是“帮助用户理解拖到哪里了”，不是新增一个独立剧情导航页面。

## 3. 明确非目标

第一版不做：

- 不做章节列表；
- 不做 `剧情要点` 按钮；
- 不做 `下一章` 快捷按钮；
- 不做上滑精调；
- 不做运行时后端截帧接口；
- 不在拖动时调用 LLM；
- 不把章节能力做成播放器右侧操作栏入口；
- 不改变现有点击播放、暂停、seek 的基础心智。

## 4. 用户体验

### 4.1 默认播放态

默认播放时，播放器仍保持现在的短剧观看界面。

唯一新增元素是进度条上的章节分界刻度：

- 刻度来源于 `story_chapters[].start_time`；
- 排除 `start_time = 0` 的第一章起点；
- 每个刻度按 `start_time / duration` 映射到进度条位置；
- 刻度是短竖线，视觉上弱于当前播放进度和 thumb；
- 如果没有章节数据，进度条退化为现有样式。

默认态不展示章节标题，避免遮挡视频和字幕。

### 4.2 拖动进度条态

用户水平拖动进度条时，进入拖动态。

拖动态在进度条上方展示：

- 当前拖动时间点对应的视频预览帧；
- 当前时间所属章节的 `title`；
- 当前拖动时间和视频总时长；
- 仍带章节刻度的进度条。

拖动态的进度条需要进入更易操作的形态：

- 进度条从默认细线变成更粗的半透明圆角条；
- thumb 从默认小圆点变成竖向白色胶囊；
- 章节刻度继续显示，但透明度降低，只作为辅助边界提示；
- 拖拽结束后恢复默认细线形态。

手势规则采用“先命中进度条，再进入全屏 scrub”的模式：

- 默认态只有进度条附近可以启动拖拽，避免误触；
- 一旦拖拽被激活，后续移动不再要求手指贴着进度条；
- 后续 scrub 只读取手指的水平 `pageX`，映射到进度条绝对坐标；
- 纵向位置不参与计算，手指滑到屏幕上方也可以继续拖动；
- scrub 激活期间禁用外层短视频列表的竖向翻页，避免纵向滑动同时触发切换视频；
- 松手后提交 seek 并退出拖动态。

拖动态下，播放器下半部分的普通观看 chrome 需要临时隐藏，包括：

- 右侧收藏、评论、点赞、分享等操作栏；
- 左下标题、标签和简介。

这样预览帧和章节标题不会与视频标题、简介或图标混在一起。顶部播放设置可以保留，因为它不占用预览区域。
底部全局 tab 保持显示，它属于 App 导航，不属于当前视频的信息层。

章节匹配规则：

```text
chapter.start_time <= drag_time < chapter.end_time
```

如果 `drag_time` 等于最后一章结束时间，则显示最后一章。

松手后：

- 调用现有 `onSeekCommit(dragTime)`；
- 播放器跳转到目标时间；
- 拖动态浮层消失；
- 播放继续。

### 4.3 缺省和失败状态

缺少 `story_chapters`：

- 不显示章节刻度；
- 拖动态不显示章节标题；
- seek 行为保持可用。

缺少 `storyboard`：

- 不显示预览帧；
- 拖动态仍显示时间；
- 如果有 `story_chapters`，仍显示章节标题。

某张 sprite sheet 加载失败：

- 当前预览帧区域隐藏或显示空态底色；
- 不阻塞 seek；
- 不影响章节标题和时间展示。

## 5. 前端组件设计

推荐直接增强现有 `PlayerControls`，不要新建一套平行时间轴。

当前 `PlayerControls` 已经负责：

- 展示进度条；
- 维护 `dragTime`；
- 根据水平拖动计算目标时间；
- 松手后调用 `onSeekCommit`。

新增职责：

- 接收可选 `storyChapters`；
- 接收可选 `storyboard`；
- 根据 `storyChapters` 渲染章节刻度；
- 在 `dragTime !== undefined` 时渲染拖动态浮层；
- 根据 `dragTime` 找到当前章节；
- 根据 `dragTime` 找到 storyboard sprite sheet 中对应 cell。

建议拆出两个轻量子组件：

```text
ChapterProgressTicks
  -> 根据 chapters + duration 渲染刻度

StoryboardPreview
  -> 根据 storyboard manifest + time 渲染 sprite sheet crop
```

`PlayerPage` 负责把当前视频的章节和 storyboard 数据传给 `PlayerControls`。

## 6. 数据结构

### 6.1 Story Chapter

前端第一版只消费这些字段：

```json
{
  "chapter_id": "ch_demo_ep01_001",
  "video_id": "demo_ep01",
  "start_time": 0.0,
  "end_time": 18.0,
  "title": "债主堵门",
  "summary": "债主上门逼债，主角试图保护家人。",
  "importance": 0.62
}
```

字段要求：

- `start_time`、`end_time` 单位为秒；
- 章节连续覆盖完整视频时间线；
- `title` 是短中文剧情标签；
- `summary` 第一版不在播放器展示，但保留给调试和后续扩展。

### 6.2 Storyboard Manifest

采用离线生成的 sprite sheet + manifest，不使用运行时截帧接口。

建议 manifest：

```json
{
  "video_id": "demo_ep01",
  "interval_seconds": 1,
  "frame_width": 160,
  "frame_height": 90,
  "columns": 5,
  "rows": 5,
  "sheets": [
    {
      "url": "/static/storyboards/demo_ep01/sheet_000.jpg",
      "start_time": 0,
      "frame_count": 25
    },
    {
      "url": "/static/storyboards/demo_ep01/sheet_001.jpg",
      "start_time": 25,
      "frame_count": 25
    }
  ]
}
```

定位规则：

```text
frame_index = floor(time_sec / interval_seconds)
sheet_index = floor(frame_index / (columns * rows))
cell_index = frame_index % (columns * rows)
cell_col = cell_index % columns
cell_row = floor(cell_index / columns)
```

前端根据 `cell_col` 和 `cell_row` 裁剪对应 sprite sheet 区域。

## 7. 离线资产生成

新增离线 storyboard 生成能力，输入为：

- `video.mp4`
- `video_id`
- 输出目录
- 采样间隔，第一版默认 `1s`
- 单帧宽度，第一版建议 `160px`；高度默认由首帧原始比例自动推导，保证缩略图和原视频画面比例一致
- sprite sheet 网格，第一版建议 `5 x 5`

输出为：

```text
storyboard_manifest.json
sheet_000.jpg
sheet_001.jpg
...
```

第一版可以先把生成结果放在本地 fixture 或服务端静态目录中，后续再接 CDN。

## 8. API / Fixture 接入

第一版可以分两步接入：

1. 先用前端 fixture 验证交互和视觉效果；
2. 再把 `story_chapters` 和 `storyboard` manifest 透传到 `PlayerVideo`。

`PlayerVideo` 建议新增可选字段：

```ts
interface PlayerVideo {
  storyChapters?: StoryChapter[];
  storyboard?: StoryboardManifest;
}
```

当前实现采用后端透传方式：

- `GET /api/videos` 和 `GET /api/videos/{video_id}` 的单个 video 对象可选返回 `story_chapters` 和 `storyboard`；
- 后端默认从 `output/story_chapter_validation/<video_id>/story_chapters.json` 读取章节；
- 后端默认从 `output/storyboards/<video_id>/storyboard_manifest.json` 读取 storyboard manifest；
- 可通过环境变量 `STORY_CHAPTER_OUTPUT_ROOT` 和 `STORYBOARD_ROOT` 覆盖这两个目录；
- `/storyboards/<video_id>/sheet_000.jpg` 作为静态资源路径托管离线生成的 sprite sheet；
- 如果 manifest 中 sheet `url` 是相对文件名，例如 `sheet_000.jpg`，后端会归一化为 `/storyboards/<video_id>/sheet_000.jpg`。

前端仍保持容错：缺少这些字段时，播放器退化为普通进度条。

## 9. 验收标准

第一版验收：

1. 默认播放态的进度条显示章节分界刻度；
2. 没有章节数据时，播放器进度条保持原样；
3. 拖动进度条时展示 storyboard 预览帧；
4. 拖动进度条时展示当前章节 title；
5. 拖动时间变化时，预览帧和章节 title 随之更新；
6. 松手后仍使用现有 seek commit 流程跳转；
7. 没有 storyboard 或图片加载失败时，不影响 seek；
8. 不出现章节列表、下一章按钮或额外剧情导航入口；
9. 拖动时隐藏播放器下半部分视频信息层，松手后恢复，但底部全局 tab 保持显示；
10. 拖动时进度条变成更粗的圆角条，thumb 变成更容易观察的竖向胶囊；
11. 拖动激活后，手指纵向离开进度条也能继续按水平位置 scrub；
12. 拖动激活期间不会触发外层视频列表的上下切换；
13. Storyboard 单帧比例与源视频画面比例一致；
14. 前端 typecheck 和相关单元测试通过。

## 10. 后续扩展

后续可以考虑：

- 根据章节重要度增强某些刻度；
- 在拖动态显示章节 summary；
- 为 storyboard 生成接入批处理脚本；
- 将 storyboard 上传 CDN；
- 在算法 viewer 中复用 storyboard 预览；
- 根据用户拖动行为评估章节切分质量。

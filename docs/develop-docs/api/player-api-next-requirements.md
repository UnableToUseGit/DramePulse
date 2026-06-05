# 播放器前端新增 API 需求

## 1. 背景

当前移动端播放器 Demo 已经从单视频播放，演进为三个主要页面：

- 首页：像短视频一样上下滑，帮助用户发现想看的剧；
- 剧场页：展示当前可播放的短剧列表；
- 剧集播放页：用户进入某部剧后，按集数继续观看。

旧接口主要围绕 `GET /api/videos` 展开。它可以返回所有可播放视频，但无法表达“首页只要每部剧第一集”“剧场只要剧列表”“进入某部剧后再按集数取视频”这些页面语义。

因此，前端需要一组更贴近产品流程的 API。目标不是做复杂平台，而是让前端不再一次性拉全量视频后自己分组、过滤和推断。

## 2. 当前问题

### 2.1 首页数据过多

首页现在直接使用 `/api/videos` 返回的全量视频。

但首页的产品目标是“发现剧”，不是“连续刷同一部剧的所有集”。首页应该只展示每部剧的第一集。

### 2.2 剧场缺少剧列表接口

剧场页需要的是“剧”的信息，例如标题、封面、总集数、是否可播放。

当前后端没有独立的剧列表接口，前端只能从全量视频中按 `series_id` 或 `series_name` 分组。这个逻辑不应该长期放在前端。

### 2.3 选剧后缺少按集请求接口

用户在剧场点进某部剧后，前端需要按集数展示和播放。

当前做法是前端启动时已经拿到了所有视频，再本地找出该剧的所有集。后续数据量变大后，这种方式会导致启动慢、请求重、状态难维护。

### 2.4 播放资产分散

播放一集视频时，前端需要：

- 视频播放地址；
- 普通弹幕；
- storyboard；
- 章节划分结果；
- 互动方案。

当前这些数据有的在 `VideoResponse` 中，有的通过单独接口获取。后端已有基础能力，但还缺少一个稳定的“播放资产加载协议”。

## 3. 建议 API

### 3.1 首页 Feed

```http
GET /api/feed/home
```

作用：

- 返回首页可刷的视频列表；
- 每部剧只返回第一集；
- 用于 App 刚打开时的首页渲染。

建议返回：

```json
{
  "videos": [
    {
      "video_id": "beipai_xunbao_biji_ep01",
      "series_id": "beipai_xunbao_biji",
      "series_name": "北派寻宝笔记",
      "title": "北派寻宝笔记 第1集",
      "episode_no": 1,
      "episode_label": "第1集",
      "duration": 126.5,
      "stream_url": "/api/videos/beipai_xunbao_biji_ep01/stream",
      "danmaku_url": "/api/videos/beipai_xunbao_biji_ep01/danmaku"
    }
  ]
}
```

说明：

- 后端负责判断“每部剧第一集”；
- 如果某部剧没有 `episode_no = 1`，可返回该剧最小 `episode_no` 的 active 视频；
- 返回结构可以复用现有 `VideoResponse`。

### 3.2 剧场剧列表

```http
GET /api/series
```

作用：

- 返回当前可播放的剧列表；
- 用于剧场页展示标题和封面；
- 不需要返回每一集的完整播放资产。

建议返回：

```json
{
  "series": [
    {
      "series_id": "beipai_xunbao_biji",
      "title": "北派寻宝笔记",
      "cover_url": "/covers/beipai_xunbao_biji.jpg",
      "summary": "民间寻宝题材短剧",
      "episode_count": 40,
      "first_video_id": "beipai_xunbao_biji_ep01",
      "status": "active"
    }
  ]
}
```

前端最关心字段：

- `series_id`
- `title`
- `cover_url`
- `episode_count`
- `first_video_id`

说明：

- `cover_url` 建议由后端提供，避免前端长期维护本地封面映射；
- MVP 阶段可以先从 `videos` 表按 `series_id` 聚合；
- 后续如果有更多剧级信息，可以再增加独立 `series` 表。

### 3.3 某部剧的剧集列表

```http
GET /api/series/{series_id}/episodes
```

作用：

- 返回某部剧的全部可播放剧集；
- 用于进入剧后播放、选集面板、续播逻辑；
- 按 `episode_no` 从小到大排序。

建议返回：

```json
{
  "series_id": "beipai_xunbao_biji",
  "series_name": "北派寻宝笔记",
  "episodes": [
    {
      "video_id": "beipai_xunbao_biji_ep01",
      "title": "北派寻宝笔记 第1集",
      "episode_no": 1,
      "episode_label": "第1集",
      "duration": 126.5,
      "stream_url": "/api/videos/beipai_xunbao_biji_ep01/stream",
      "danmaku_url": "/api/videos/beipai_xunbao_biji_ep01/danmaku"
    }
  ]
}
```

说明：

- 前端进入某部剧时请求这个接口；
- 前端不再依赖启动时获取到全量视频；
- 返回的 episode 对象可以继续复用现有 `VideoResponse`。

### 3.4 按集获取单个视频

```http
GET /api/series/{series_id}/episodes/{episode_no}
```

作用：

- 按剧和集数获取一个视频；
- 用于前端直接跳转到某一集；
- 也方便后续从分享链接、推荐卡片、Story Q&A 跳转到指定剧集。

建议返回：

```json
{
  "video_id": "beipai_xunbao_biji_ep03",
  "series_id": "beipai_xunbao_biji",
  "series_name": "北派寻宝笔记",
  "title": "北派寻宝笔记 第3集",
  "episode_no": 3,
  "episode_label": "第3集",
  "duration": 129.2,
  "stream_url": "/api/videos/beipai_xunbao_biji_ep03/stream",
  "danmaku_url": "/api/videos/beipai_xunbao_biji_ep03/danmaku"
}
```

说明：

- 这个接口不是必须第一时间实现；
- 如果前端已经通过 `GET /api/series/{series_id}/episodes` 拿到全部剧集，可以先不单独请求；
- 但从长期接口语义看，保留它会更清晰。

### 3.5 播放资产

```http
GET /api/videos/{video_id}/playback-assets
```

作用：

- 返回播放一集视频所需的非视频流资产；
- 用于统一弹幕、storyboard、章节和互动方案的加载；
- 让前端不需要自己拼多个接口并处理不同缺省情况。

建议返回：

```json
{
  "video": {
    "video_id": "beipai_xunbao_biji_ep01",
    "series_id": "beipai_xunbao_biji",
    "series_name": "北派寻宝笔记",
    "episode_no": 1,
    "stream_url": "/api/videos/beipai_xunbao_biji_ep01/stream"
  },
  "danmaku": {
    "available": true,
    "items": []
  },
  "storyboard": {
    "video_id": "beipai_xunbao_biji_ep01",
    "interval_seconds": 2,
    "frame_width": 160,
    "frame_height": 90,
    "columns": 5,
    "rows": 5,
    "sheets": []
  },
  "story_chapters": [],
  "interaction_plans": []
}
```

说明：

- 视频本体仍通过 `stream_url` 播放，不放进这个接口；
- `storyboard` 和 `story_chapters` 可以复用现有 `VideoResponse` 中的字段；
- `interaction_plans` 可以复用现有 `/api/videos/{video_id}/interaction-plans` 的结构；
- 如果某类资产暂时没有，返回空数组或 `available: false`，不要让整个接口失败。

## 4. 保留现有 API

以下接口仍然有价值，建议保留：

```http
GET /api/videos
GET /api/videos/{video_id}
GET /api/videos/{video_id}/stream
GET /api/videos/{video_id}/danmaku
GET /api/videos/{video_id}/interaction-plans
POST /api/events
```

说明：

- `/api/videos` 可以继续作为调试或后台管理用的全量视频列表；
- `/api/videos/{video_id}` 继续作为按 `video_id` 获取视频详情的基础接口；
- `/stream`、`/danmaku`、`/interaction-plans` 继续保留，方便单独调试和缓存；
- 新增 API 主要负责页面语义和前端加载流程。

## 5. 数据来源建议

MVP 阶段可以先不新增复杂表结构。

短期做法：

- 首页 feed：从 `videos` 表按 `series_id` 分组，取每组最小 `episode_no`；
- 剧列表：从 `videos` 表按 `series_id` 聚合出 `series_name`、`episode_count`、`first_video_id`；
- 封面：先增加一个轻量配置或字段，让后端返回 `cover_url`；
- 播放资产：继续从现有视频表、弹幕文件、storyboard 输出、章节输出和互动方案表读取。

长期做法：

- 增加 `series` 表，保存 `series_id`、`title`、`cover_url`、`summary`、`status`、`sort_rank`；
- `videos` 表继续保存分集信息；
- 离线算法和素材准备流程只负责生成资产，FastAPI 负责读取并下发资产。

## 6. 建议实施顺序

1. 新增 `GET /api/feed/home`，让首页只展示每部剧第一集。
2. 新增 `GET /api/series`，让剧场页直接请求剧列表和封面。
3. 新增 `GET /api/series/{series_id}/episodes`，让进入某部剧后再请求剧集。
4. 新增 `GET /api/videos/{video_id}/playback-assets`，统一播放资产加载。
5. 视需要再补 `GET /api/series/{series_id}/episodes/{episode_no}`。

这样可以先解决当前前端最明显的数据语义问题，再逐步整理播放资产协议。

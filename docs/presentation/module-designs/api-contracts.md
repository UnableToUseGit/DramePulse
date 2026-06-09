# API 契约设计

## 1. 模块定位

API 契约连接播放器、后端服务和数据层，目标是让前端稳定获取视频、弹幕、互动方案，并把用户事件回传到后端。

## 2. MVP 接口

### 2.1 健康检查

```http
GET /api/health
```

用于确认服务可用。

### 2.2 获取视频列表

```http
GET /api/videos
```

用于获取可播放视频列表。

### 2.3 获取视频详情

```http
GET /api/videos/{video_id}
```

用于获取标题、剧名、集数、时长和播放地址。

### 2.4 获取视频流

```http
GET /api/videos/{video_id}/stream
```

用于播放器实际加载视频。

### 2.5 获取普通弹幕

```http
GET /api/videos/{video_id}/danmaku
```

用于播放器弹幕层渲染。

### 2.6 获取互动方案

```http
GET /api/videos/{video_id}/interaction-plans
```

用于播放器根据 `trigger_time` 自动触发互动。

### 2.7 上报用户事件

```http
POST /api/events
```

用于上报互动曝光、点击、反馈展示、自然消失等事件。

### 2.8 查询互动结果

```http
GET /api/interactions/{interaction_id}/results
```

用于查询选项点击分布和共鸣反馈。

## 3. 当前实现草稿

当前 FastAPI 后端已经提供视频、弹幕、互动方案、用户事件、播放事件和 Story Q&A 相关接口。

后续需要补充每个接口的请求/响应样例、字段说明、错误码和演示调用方式。

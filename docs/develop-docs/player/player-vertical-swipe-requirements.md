# 播放器上下滑切换视频需求说明

## 1. 背景

当前 `apps/player-demo` 已经完成播放器从后端获取真实数据：

- `GET /api/videos` 获取视频列表；
- `GET /api/videos/{video_id}/stream` 播放视频；
- `GET /api/videos/{video_id}/danmaku` 获取弹幕；
- 前端当前只取第一条视频播放。

下一步希望把播放器体验从“单视频播放”升级为接近短视频 App 的“上下滑切换视频”。

本需求只关注播放器基础能力，不包含互动机制、`Interaction Plan`、投票条或高光点触发。

## 2. 目标

实现一个移动端短剧播放器 Feed：

```text
用户上滑 -> 切到下一集/下一条视频
用户下滑 -> 切到上一集/上一条视频
```

切换后：

1. 当前视频停止；
2. 新视频使用对应 `stream_url` 播放；
3. 弹幕使用对应 `danmaku_url` 加载；
4. 播放进度重置为 `0`；
5. 播放状态、弹幕状态、seek 状态重置；
6. 页面展示当前视频的剧名、集数和标题。

## 3. 推荐实现方案

推荐使用 React Native 的 `FlatList` + `pagingEnabled`，不要用简单 `PanResponder` 直接切换。

原因：

- `FlatList pagingEnabled` 更接近真实短视频 App 的手感；
- 拖动时当前页和下一页能自然跟手；
- 松手后系统自动吸附到上一页/下一页；
- 后续可以扩展预加载、只播放可见页、回收不可见页；
- 比手写 PanResponder 切屏动画更稳定。

建议结构：

```tsx
<FlatList
  data={videos}
  pagingEnabled
  showsVerticalScrollIndicator={false}
  keyExtractor={(item) => item.videoId}
  renderItem={({ item, index }) => (
    <PlayerPage
      video={item}
      isActive={index === activeIndex}
    />
  )}
  onMomentumScrollEnd={handlePageChanged}
/>
```

## 4. 数据流

前端启动后：

1. 请求 `GET /api/videos`；
2. 将后端返回的每条视频归一化为前端 `PlayerVideo`；
3. 渲染全屏竖向分页列表；
4. 每个 `PlayerPage` 根据自己的 `danmaku_url` 加载弹幕；
5. 只有当前可见页允许播放视频和展示弹幕。

当前后端返回的视频字段示例：

```json
{
  "video_id": "beipai_xunbao_biji_ep01",
  "series_name": "北派寻宝笔记",
  "title": "第1集标题",
  "episode_no": 1,
  "episode_label": "ep01",
  "duration": 123.45,
  "stream_url": "/api/videos/beipai_xunbao_biji_ep01/stream",
  "danmaku_url": "/api/videos/beipai_xunbao_biji_ep01/danmaku"
}
```

前端使用时需要把相对 URL 拼成绝对 URL：

```text
http://127.0.0.1:8000 + stream_url
http://127.0.0.1:8000 + danmaku_url
```

如果用手机真机调试，不能使用 `127.0.0.1`，需要改成 Mac 的局域网 IP。

## 5. 播放行为要求

### 5.1 当前页播放

只有当前页 `isActive === true` 时：

- 可以播放视频；
- 可以响应点击播放/暂停；
- 可以推进弹幕；
- 可以响应进度条拖拽。

非当前页：

- 视频应暂停；
- 弹幕不推进；
- 不响应播放控制。

### 5.2 页面切换

当 `activeIndex` 改变时：

- 新页面 `currentTime` 重置为 `0`；
- 新页面 `isStarted` 重置为 `false`，或者按产品需要自动播放；
- 新页面重新计算弹幕起始位置；
- 旧页面暂停并清理正在飞行的弹幕。

第一版建议：切到新视频后展示“点击播放短剧”，不自动播放。这样更容易调试，也避免多视频同时播放。

### 5.3 边界状态

当用户在第一条视频继续下滑，或在最后一条视频继续上滑：

- 不需要弹 toast；
- 保持当前页即可；
- `FlatList` 默认边界回弹可以接受。

## 6. 弹幕要求

每个视频使用自己的 `danmaku_url` 获取弹幕：

```text
GET /api/videos/{video_id}/danmaku
```

返回示例：

```json
{
  "video_id": "beipai_xunbao_biji_ep01",
  "available": true,
  "count": 123,
  "items": [
    {
      "danmaku_id": "d1",
      "time_sec": 12.3,
      "text": "太爽了",
      "digg_count": 8,
      "score": 9.5
    }
  ]
}
```

如果 `available === false`，前端展示视频但不展示弹幕。

第一版可以继续复用现有：

- `DanmakuLayer`
- `danmakuScheduler`
- `danmakuSampling`

## 7. UI 要求

保持现有播放器视觉，不做大改版。

每页应展示：

- 视频画面；
- 播放/暂停状态提示；
- 进度条；
- 右侧操作栏；
- 底部剧名、集数、标题；
- 弹幕层。

底部文案建议：

```text
i说 系列剧 · {series_name}
{title}
{episode_label} · 真实弹幕
```

## 8. 非目标

第一版不做：

- `Interaction Plan` 触发；
- 高光点投票条；
- 用户事件上报；
- 视频预加载优化；
- 无限加载；
- 服务端分页；
- 自动连播策略；
- 复杂转场动画；
- 原生手势库引入。

## 9. 验收标准

1. 启动后端和前端后，播放器从 `GET /api/videos` 获取视频列表；
2. 首屏能播放后端返回的第一条视频；
3. 首屏弹幕来自该视频的 `danmaku_url`；
4. 上滑后切到下一条视频；
5. 下滑后切回上一条视频；
6. 切换视频后标题、剧名、集数随当前视频变化；
7. 切换视频后弹幕也随当前视频变化；
8. 非当前页视频不会继续播放；
9. `npm run typecheck` 通过；
10. 现有 domain 测试通过。

## 10. 建议拆分

建议分两步实现：

### Step 1：数据层升级

- `playerApi` 从只返回第一条视频，改成返回 `videos: PlayerVideo[]`；
- 增加按 `video.danmakuUrl` 加载弹幕的方法；
- 增加对应单元测试。

### Step 2：播放器分页

- 新增 `PlayerPage` 组件，承载单个视频页；
- `PlayerScreen` 使用 `FlatList pagingEnabled` 渲染多个 `PlayerPage`；
- 维护 `activeIndex`；
- 只有 active page 播放视频和弹幕。

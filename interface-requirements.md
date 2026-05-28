# 前端接口需求

## 1. 目标

本文档只描述 DramePulse 当前移动端播放器 Demo 所需的前端接口。

目标不是把后端做成完整平台，而是先让前端能稳定完成这条最小闭环：

```text
视频列表 -> 播放视频 -> 拉取弹幕 -> 拉取互动方案 -> 触发投票 -> 上报事件
```

当前前端是 React Native + Expo Demo，接口设计优先满足以下原则：

- 接口粒度清楚，前端容易接；
- 返回结构稳定，便于后续替换成真实服务；
- 先支持本地静态资源和本地数据库，后续再迁移到 OSS / 云存储；
- 前端只认 `video_id`、`interaction_id` 这类稳定业务 ID，不依赖爬虫原始文件名。

## 2. 当前 MVP 必需接口

### 2.1 获取视频列表

```http
GET /api/videos
```

用途：

- 获取当前后端可播放的视频 ID；
- 前端后续再用 `video_id` 请求单个视频详情、弹幕和互动方案。

返回示例：

```json
{
  "videos": [
    { "video_id": "v_001" },
    { "video_id": "v_002" }
  ]
}
```

前端最关心的字段：

- `video_id`

说明：

- 列表接口只承担“告诉前端有哪些视频”的职责；
- 播放地址、标题、时长等详细信息放在单个视频详情接口里；
- 如果 demo 阶段不做列表页，前端也可以直接使用默认 `video_id` 请求详情。

---

### 2.2 获取单个视频详情

```http
GET /api/videos/{video_id}
```

用途：

- 前端进入播放页时补全视频元数据；
- 也可以用于播放器页的 debug 信息。

返回示例：

```json
{
  "video_id": "v_001",
  "title": "第 1 集",
  "series_name": "十八岁太奶奶驾到，重整家族荣耀第三部",
  "episode_no": 1,
  "duration_ms": 124700,
  "url": "http://localhost:8000/static/videos/v_001.mp4",
  "source": "local"
}
```

前端最关心的字段：

- `video_id`
- `title`
- `series_name`
- `episode_no`
- `duration_ms`
- `url`
- `source`

说明：

- `url` 是前端实际播放地址，不再使用 `stream_url` 命名；
- `duration_ms` 使用毫秒，避免秒级浮点误差；
- `episode_no` 表示集数，不使用 `current_episode`，避免和播放状态混淆；
- `series_name` 用于播放器标题或后续列表展示；
- `source` 用于标记视频来源，例如 `local`、`oss`、`cdn`。

---

### 2.3 获取普通弹幕

```http
GET /api/videos/{video_id}/danmaku
```

用途：

- 直接透传爬虫保存下来的原始弹幕文件；
- 后端只负责按 `video_id` 找到对应文件并返回；
- 前端自行做移动端采样和展示节流。

返回示例：

```json
{
  "video_id": "v_001",
  "danmaku": [
    {
      "danmaku_id": "7546167220452232475",
      "item_id": "7632154313724267830",
      "user_id": "145581627423950",
      "time_ms": 585,
      "time_sec": 0.585,
      "text": "坏菜了",
      "digg_count": 78,
      "score": 68.1777402742,
      "has_emoji": false,
      "danmaku_type": 0,
      "is_ad": false,
      "raw": {
        "offset_time": 585,
        "text": "坏菜了",
        "status": 1
      }
    }
  ]
}
```

前端最关心的字段：

- `danmaku_id`
- `item_id`
- `user_id`
- `time_ms`
- `time_sec`
- `text`
- `digg_count`
- `score`

说明：

- 后端不做采样、不做二次整理；
- 返回内容以爬虫原始文件里的 `danmaku` 数组为准；
- 前端只消费自己需要的字段，其余字段可以原样保留。

---

### 2.4 获取互动方案

```http
GET /api/videos/{video_id}/interaction-plans
```

用途：

- 前端根据 `trigger_time` 自动触发互动；
- 这是播放器内互动系统的核心输入。

返回示例：

```json
{
  "video_id": "v_001",
  "interaction_plans": [
    {
      "interaction_id": "i_001",
      "highlight_id": "h_001",
      "video_id": "v_001",
      "trigger_time": 38.0,
      "expire_time": 46.0,
      "interaction_type": "danmaku_poll",
      "question": "这波反转你怎么看？",
      "options": [
        {
          "option_id": "o_001",
          "text": "卧槽反转了",
          "danmaku_text": "卧槽反转了！",
          "rank": 1,
          "base_score": 0.8
        }
      ],
      "feedback": {
        "type": "poll_result",
        "show_ratio": true,
        "show_resonance_text": true,
        "resonance_text_template": "你和 {ratio}% 的观众一样选择了「{option}」"
      },
      "display_position": "subtitle_safe_area",
      "status": "active"
    }
  ]
}
```

前端最关心的字段：

- `interaction_id`
- `highlight_id`
- `video_id`
- `trigger_time`
- `interaction_type`
- `question`
- `options`
- `feedback`
- `status`

说明：

- 前端当前只使用 `trigger_time` 判断触发；
- `expire_time` 可以先保留在返回里，但前端不拿它控制 UI 展示时长；
- 当前 A 版只需要 `interaction_type = "danmaku_poll"`；
- 后续如果增加别的互动类型，前端再按 `interaction_type` 分发。

---

### 2.5 上报用户事件

```http
POST /api/events
```

用途：

- 上报曝光、点击、反馈、消失等互动事件；
- 也可上报播放事件、seek 事件、暂停事件；
- 后端可先复用现有播放事件表或独立事件表，接口层先统一即可。

请求示例：

```json
{
  "event_type": "option_click",
  "user_id": "u_demo_001",
  "video_id": "v_001",
  "highlight_id": "h_001",
  "interaction_id": "i_001",
  "option_id": "o_001",
  "client_time": 38.6,
  "timestamp": 1779267600,
  "extra": {
    "interaction_type": "danmaku_poll",
    "device": "expo_go"
  }
}
```

返回示例：

```json
{
  "event_id": "evt_001",
  "accepted": true
}
```

前端最关心的字段：

- 请求成功即可；
- 如果后续接入埋点回执，再看 `event_id`。

建议支持的事件类型：

- `interaction_exposure`
- `option_click`
- `feedback_shown`
- `interaction_dismiss`
- `pause`
- `resume`
- `seek_forward`
- `seek_backward`

---

### 2.6 健康检查

```http
GET /api/health
```

用途：

- 本地开发时确认后端已启动；
- 便于前端和队友排障。

返回示例：

```json
{
  "status": "ok",
  "service": "dramepulse-api"
}
```

# 移动端播放器 Demo 模块设计

## 1. 模块定位

移动端播放器 Demo 是 DramePulse 第一版面向评审展示的体验层入口。

它不是泛视频 App，也不是完整红果剧场复刻，而是在短剧 App 的真实观看场景中验证 DramePulse 的即时互动闭环：

```text
Interaction Plan
  ↓
移动端播放器播放到高光点
  ↓
中间弹幕投票条自动触发
  ↓
用户低摩擦点击
  ↓
比例反馈与共鸣弹幕
  ↓
端内事件流与本地统计更新
```

第一版只做单个短剧播放页，不做剧场列表、搜索、账号、支付、商城、推荐流或完整后台服务。

## 2. 设计目标

第一版实现优先满足以下目标：

1. 在 iOS 和 Android 真机上通过 Expo Go 体验；
2. 高保真贴近红果剧场式竖屏短剧播放页，让评委快速理解使用场景；
3. 播放到高光点时自动触发互动，不要求用户主动寻找入口；
4. 互动形式为屏幕中间的弹幕投票条，不暂停播放，不清空普通弹幕；
5. 用户点击后立即展示投票比例和共鸣弹幕；
6. 端内记录曝光、点击、反馈展示等事件，并在 debug 面板中展示本地事件流和统计；
7. 为后续接入真实 `POST /api/events` 和策略更新服务保留数据契约边界。

## 3. 体验范围

### 3.1 包含

- 竖屏短剧播放；
- 普通弹幕展示；
- 高光点自动触发互动；
- 中间弹幕投票条；
- 点击后的比例反馈；
- 点击后的共鸣弹幕；
- 右上角 debug 开关；
- 端内事件流；
- 端内统计计数。

### 3.2 暂不包含

- 剧场列表页；
- 首页、我的、商城等完整 App 外壳；
- 用户登录；
- 真实评论系统；
- 真实点赞、收藏、分享后端；
- 真实 `POST /api/events`；
- 服务端统计聚合；
- 策略更新服务；
- iOS TestFlight 或 Android APK 作为第一版完成条件。

## 4. 界面设计

### 4.1 页面基调

播放页默认直接进入短剧观看状态，视觉结构高保真贴近红果剧场播放页：

- 全屏竖屏视频作为主背景；
- 顶部保留状态栏感、菜单和搜索/调试入口；
- 右侧保留收藏、评论、点赞、分享等纵向操作按钮；
- 底部保留剧集标题、标签、简介、选集入口和底部 tab 氛围；
- 普通弹幕在视频上持续滚动。

页面借鉴红果剧场的观看语境和信息密度，但 DramePulse 的核心新增能力必须是视觉主角。

### 4.2 互动投票条

互动投票条位于屏幕中间区域。

触发时机来自 `Interaction Plan.trigger_time`。播放器当前时间进入触发窗口后，系统自动展示投票条。

投票条设计原则：

- 像一条被系统聚合出来的高级弹幕；
- 不做大卡片；
- 不暂停视频；
- 不清空普通弹幕；
- 不遮挡底部剧集信息；
- 默认深色半透明毛玻璃背景；
- 白色主文案；
- 选项使用深色胶囊按钮；
- 点击态和结果态使用红橙色点亮。

典型内容：

```text
这波反转你怎么看？  [爽到了] [太离谱了] [再看一遍]
```

### 4.3 点击反馈

用户点击某个选项后，反馈分两层：

1. 投票条变为结果态，例如：

```text
你和 68% 的观众一样选择了「爽到了」
```

2. 同时生成 2 到 3 条共鸣弹幕，例如：

```text
爽到了！
这波反转绝了
姐妹们懂我
```

结果态中的比例数字、被选选项和关键提示使用红橙色强调。普通弹幕继续保留，形成真实观看氛围。

### 4.4 Debug 面板

右上角放置轻量 debug 图标。默认关闭时页面尽量像真实短剧 App；打开后展示 DramePulse 的算法与事件信息。

debug 面板展示：

- 当前 `highlight_id`；
- `highlight_type`；
- `confidence`；
- `trigger_time`；
- 当前触发的 `interaction_id`；
- 互动曝光、选项点击、反馈展示事件；
- 本地统计计数；
- 已触发/未触发的高光点状态。

debug 面板只用于评审展示和开发调试，不作为普通用户界面。

## 5. 数据输入

第一版使用本地 fixture，不接真实后端。

### 5.1 视频数据

```text
data/case1/ep01.mp4
```

用于短剧播放。

### 5.2 弹幕数据

```text
data/case1/ep01.json
```

读取其中 `danmaku` 数组，用于普通弹幕展示。

### 5.3 互动方案

```text
example_output/case1_ep01/interaction_plan_generation.json
```

读取其中 `interaction_plans` 数组。每个 `Interaction Plan` 至少消费以下字段：

- `interaction_id`
- `highlight_id`
- `video_id`
- `trigger_time`
- `expire_time`
- `interaction_type`
- `question`
- `options`
- `feedback`
- `display_position`
- `status`

第一版只渲染 `interaction_type = "danmaku_poll"`。

## 6. 端内事件

第一版不接真实事件 API，但事件结构应对齐 `packages/contracts/schemas/user-event.schema.json`。

需要记录的事件：

- `interaction_exposure`：互动投票条曝光；
- `option_click`：用户点击选项；
- `feedback_shown`：反馈展示；
- `interaction_dismiss`：互动自然消失或被关闭。

事件至少包含：

- `event_type`
- `user_id`
- `video_id`
- `highlight_id`
- `interaction_id`
- `option_id`
- `client_time`
- `timestamp`
- `extra`

示例：

```json
{
  "event_type": "option_click",
  "user_id": "u_demo_001",
  "video_id": "case1_ep01",
  "highlight_id": "h_case1_ep01_002",
  "interaction_id": "i_h_case1_ep01_002",
  "option_id": "o_h_case1_ep01_002_001",
  "client_time": 34.2,
  "timestamp": 1779370000,
  "extra": {
    "interaction_type": "danmaku_poll",
    "device": "expo_go"
  }
}
```

## 7. 本地统计

第一版在端内维护最小统计，用于 debug 面板展示闭环效果。

统计指标：

- `exposure_count`
- `click_count`
- `feedback_shown_count`
- `dismiss_count`
- `option_click_count`
- `option_click_rate`

这些统计只用于 demo 展示，不写入持久化存储。后续服务端版本可迁移到 `services/` 中的事件接收与统计聚合模块。

## 8. 技术方案

使用 React Native + Expo + TypeScript。

建议目录：

```text
apps/player-demo/
```

技术选择：

- Expo managed workflow；
- React Native；
- TypeScript；
- `expo-video` 作为视频播放层；
- 本地 fixture 作为数据输入；
- 端内状态管理第一版使用 React state；
- 图标优先使用 `lucide-react-native` 或 Expo 生态兼容图标。

交付方式：

1. 第一阶段通过 Expo Go 真机预览；
2. iOS 和 Android 都需要能扫码运行；
3. 后续需要正式安装包时，再配置 EAS Build；
4. 如果需要优先产物，先考虑 Android APK。

## 9. 组件拆分

建议组件边界如下：

- `PlayerScreen`：播放页总入口，负责组合视频、弹幕、互动、debug；
- `VideoStage`：视频播放与当前时间监听；
- `DanmakuLayer`：普通弹幕展示；
- `InteractionPollBar`：中间弹幕投票条；
- `FeedbackBurst`：点击后的共鸣弹幕与结果反馈；
- `PlayerChrome`：顶部、右侧按钮、底部剧集信息和底部 tab；
- `DebugPanel`：高光、互动、事件流、统计展示。

核心状态流：

```text
VideoStage currentTime
  ↓
PlayerScreen 判断是否进入 trigger_time
  ↓
InteractionPollBar 曝光
  ↓
用户点击 option
  ↓
记录 User Event
  ↓
更新本地统计
  ↓
FeedbackBurst 展示比例反馈和共鸣弹幕
  ↓
DebugPanel 展示事件与统计
```

## 10. 验收标准

第一版完成时，需要满足：

1. iPhone 和 Android 真机均可通过 Expo Go 打开；
2. 打开后直接进入竖屏短剧播放页；
3. 视频可正常播放；
4. 普通弹幕可在视频上滚动；
5. 播放到高光点时，中间弹幕投票条自动出现；
6. 点击选项后，投票条变为比例结果态；
7. 点击后出现 2 到 3 条共鸣弹幕；
8. 右上角 debug 图标可以打开/关闭面板；
9. debug 面板能看到事件流和本地统计变化；
10. 页面不依赖真实后端服务即可完成演示。

## 11. 后续扩展

第一版完成后，可以继续扩展：

- 接入真实 `POST /api/events`；
- 增加服务端统计聚合；
- 接入策略更新模块；
- 在进度条上展示高光标记；
- 支持更多互动类型，例如剧情预测、角色应援、再看一遍；
- 配置 EAS Build 产出 Android APK；
- 根据评审反馈再决定是否补剧场列表页。

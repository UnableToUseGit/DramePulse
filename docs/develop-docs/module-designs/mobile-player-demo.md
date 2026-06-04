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
比例结果态反馈
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
5. 用户点击后立即展示投票比例结果态，结果态短暂停留后自动消失；
6. 端内记录曝光、点击、反馈展示、自然消失等事件，并在本地状态中维护统计；
7. 为后续接入真实 `POST /api/events` 和策略更新服务保留数据契约边界。

## 3. 体验范围

### 3.1 包含

- 竖屏短剧播放；
- 普通弹幕展示；
- 高光点自动触发互动；
- 中间弹幕投票条；
- 点击后的比例反馈；
- 真实爬取弹幕的移动端采样展示；
- 播放、暂停、拖拽进度条；
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
- 点击后的共鸣弹幕；
- 右上角 debug 面板；
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

触发时机来自 `Interaction Plan.trigger_time`。播放器当前时间到达触发点后，系统自动展示投票条。

当前前端不使用 `expire_time` 控制 UI 展示时长。`expire_time` 仍作为后端互动方案字段保留，但它是否进入最终契约还未定稿。

当前 UI 展示时长由前端控制：

- 投票态展示 3 秒；用户未点击则自动消失，并记录 `interaction_dismiss`；
- 用户点击后进入结果态，结果态展示 2 秒后自动消失；
- 同一个 `interaction_id` 完成后不重复触发；
- seek 到未完成互动的触发点之后，可以触发对应投票。

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

用户点击某个选项后，投票条变为结果态，例如：

```text
你和 68% 的观众一样选择了「爽到了」
```

结果态中的比例数字、被选选项和关键提示使用红橙色强调。普通弹幕继续保留，形成真实观看氛围。

点击后的共鸣弹幕作为下一阶段扩展，不在当前 A 版互动闭环中实现。后续实现时，应复用普通弹幕层的运行模型，而不是增加独立的静态飘层。

### 4.4 Debug 面板

播放器存在两类不同用途的 debug 信息：

- Home Feed 播放观测：用于开发阶段定位 Feed 切换、播放器加载和首帧卡顿；
- DramePulse 算法与互动事件：用于评审展示高光、互动和本地统计闭环。

Home Feed 播放观测已经实现，仅在 `__DEV__` 下显示右上角 `DBG` 入口。面板默认关闭，关闭时仍继续采集本次运行的内存事件；打开后展示：

- 当前活动页和视频 ID；
- 已挂载页面的预加载、播放权、播放器状态、真实播放和静音状态；
- 活动页变化到真实播放、首帧渲染的耗时；
- 最近 Feed 和 `expo-video` 事件。

完整播放观测事件同时使用 `[HomeFeedPlayback]` 前缀输出到终端。该观测链路不持久化、不上报后端，也不属于业务 `User Event`。

算法与互动事件 debug 面板仍未恢复。后续恢复时，默认关闭时页面尽量像真实短剧 App；打开后展示：

- 当前 `highlight_id`；
- `highlight_type`；
- `confidence`；
- `trigger_time`；
- 当前触发的 `interaction_id`；
- 互动曝光、选项点击、反馈展示事件；
- 本地统计计数；
- 已触发/未触发的高光点状态。

两类 debug 面板都不作为普通用户界面。播放观测当前不覆盖 Series Feed、广告页、弹幕和互动组件渲染成本。

### 4.5 普通弹幕

普通弹幕来自真实爬取数据，但移动端不会原样展示全量弹幕。当前实现先做移动端采样：

- 从 `data/case1/ep01.json` 的全量弹幕中读取 `danmaku` 数组；
- 每 1 秒时间桶最多保留 1 条；
- 全局相邻展示弹幕间隔必须大于 1 秒；
- 过滤过长文本；
- 同桶内优先选择 `digg_count` 和 `score` 更高、文本更短的弹幕。

当前样例中，原始弹幕约 352 条，移动端采样后约 62 条。

弹幕运行模型参考 `docs/references/Danmaku`：

- 弹幕层维护 `runningList`；
- 每条弹幕进入屏幕后测量实际宽高；
- 位移按舞台宽度、弹幕宽度和统一速度计算；
- 只有当 `x + width < 0`，即整条弹幕完全离开屏幕后才移除；
- 暂停时停止 RAF，保留当前弹幕位置；
- seek 后清空当前弹幕，重置发射位置，当前时间点之后的弹幕从右侧重新进入。

## 5. 数据输入

第一版使用本地 fixture，不接真实后端。这里的 fixture 应理解为后端 API response 的本地替身，而不是前端写死策略。

### 5.1 视频数据

```text
data/case1/ep01.mp4
```

用于短剧播放。Expo app 内复制到：

```text
apps/player-demo/assets/video/ep01.mp4
```

### 5.2 弹幕数据

```text
data/case1/ep01.json
```

读取其中 `danmaku` 数组，用于普通弹幕展示。

Expo app 内复制到：

```text
apps/player-demo/src/fixtures/danmaku.json
```

前端读取后先 normalize，再调用 `sampleMobileDanmaku` 做移动端采样。

### 5.3 互动方案

```text
output/case1_ep01/interaction_plan_generation.json
```

读取其中 `interaction_plans` 数组。每个 `Interaction Plan` 至少消费以下字段：

- `interaction_id`
- `highlight_id`
- `video_id`
- `trigger_time`
- `interaction_type`
- `question`
- `options`
- `feedback`
- `display_position`
- `status`

第一版只渲染 `interaction_type = "danmaku_poll"`。

当前 Expo app 使用本地文件模拟后端响应：

```text
apps/player-demo/src/fixtures/interaction-plan-generation.json
```

当前前端只使用 `trigger_time` 判断是否触发。`expire_time` 暂时不参与前端 UI 控制，字段是否保留等待后续契约确认。

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

第一版在端内维护最小统计，用于后续 debug 面板和答辩展示闭环效果。

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
- 图标使用 Expo 自带的 `@expo/vector-icons`，避免 React 19 peer dependency 冲突。

交付方式：

1. 第一阶段通过 Expo Go 真机预览；
2. iOS 和 Android 都需要能扫码运行；
3. 后续需要正式安装包时，再配置 EAS Build；
4. 如果需要优先产物，先考虑 Android APK。

## 9. 组件拆分

建议组件边界如下：

- `PlayerScreen`：播放页总入口，负责组合视频、弹幕和互动；
- `VideoStage`：视频播放与当前时间监听；
- `DanmakuLayer`：普通弹幕展示；
- `InteractionPollBar`：中间弹幕投票条；
- `FeedbackBurst`：预留组件，后续用于点击后的共鸣弹幕；
- `PlayerChrome`：顶部、右侧按钮、底部剧集信息和底部 tab；
- `DebugPanel`：预留组件，后续用于高光、互动、事件流、统计展示；
- `danmakuSampling`：将真实全量弹幕采样为适合移动端展示的低密度弹幕；
- `danmakuScheduler`：维护弹幕 `runningList`、seek 定位和离屏移除；
- `interactionScheduler`：根据 `trigger_time` 和已完成 interaction 判断是否触发投票；
- `events`：创建本地 `UserEvent` 并更新端内统计。

核心状态流：

```text
VideoStage currentTime
  ↓
PlayerScreen 判断是否达到 trigger_time
  ↓
InteractionPollBar 曝光
  ↓
用户点击 option
  ↓
记录 User Event
  ↓
更新本地统计
  ↓
InteractionPollBar 展示比例结果态
  ↓
结果态 2 秒后自动消失
```

## 10. 验收标准

第一版完成时，需要满足：

1. iPhone 和 Android 真机均可通过 Expo Go 打开；
2. 打开后直接进入竖屏短剧播放页；
3. 视频可正常播放；
4. 普通弹幕可在视频上滚动；
5. 播放到高光点时，中间弹幕投票条自动出现；
6. 点击选项后，投票条变为比例结果态；
7. 用户不点击时，投票条 3 秒后自动消失并记录 dismiss；
8. 用户点击后，结果态 2 秒后自动消失；
9. seek 后普通弹幕清空并从当前时间点重新进入；
10. 普通弹幕不会在未完全离屏前被提前移除；
11. 页面不依赖真实后端服务即可完成演示。

## 11. 后续扩展

第一版完成后，可以继续扩展：

- 接入真实 `POST /api/events`；
- 接入真实 `GET /api/interaction-plans`；
- 恢复算法与互动事件 debug 面板，展示事件流和本地统计变化；
- 点击后生成 2 到 3 条共鸣弹幕；
- 增加服务端统计聚合；
- 接入策略更新模块；
- 在进度条上展示高光标记；
- 支持更多互动类型，例如剧情预测、角色应援、再看一遍；
- 配置 EAS Build 产出 Android APK；
- 根据评审反馈再决定是否补剧场列表页。

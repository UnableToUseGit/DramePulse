# Home Feed 视频播放观测设计

## 1. 背景

当前移动端播放器的主线任务调整为优化视频播放和竖滑 Feed，第一阶段只聚焦 Home Feed。

虽然视频源可以是本地文件，页面切换仍可能出现卡顿。切换成本不仅来自网络，还可能来自：

- `VideoPlayer` 创建和释放；
- 视频资源加载、解码器启动和首帧渲染；
- Feed 页面挂载、卸载和相邻页预加载；
- 当前活动页变化与播放器真实播放状态之间的时序；
- 多个已挂载播放器之间的播放权竞争。

在继续优化前，需要建立可靠的观测手段，让开发者能够回答：

1. 用户开始滑动后，Feed 何时认定新的活动页？
2. 当前页和相邻页何时挂载、预加载、加载完成和释放？
3. 哪个页面拥有播放权，哪个 `VideoPlayer` 实际处于播放状态？
4. 活动页切换到真正开始播放、真正渲染首帧分别耗时多久？
5. 卡顿发生时，最近的 Feed 和播放器事件顺序是什么？

## 2. 目标

第一版观测能力需要满足：

- 仅用于 Home Feed 视频播放和 Feed 生命周期调试；
- 仅在开发模式中启用；
- 在真机屏幕内提供低干扰的状态摘要；
- 在终端输出完整、结构化、可排序的事件流；
- 使用内存保存本次运行的最近事件，不持久化、不上报后端；
- 不改变播放器控制逻辑，不影响正常观看和 Feed 滑动；
- 为后续播放器和 Feed 性能优化提供可验证的数据基础。

## 3. 非目标

第一版暂不包含：

- Series Feed 和广告页观测；
- 弹幕、互动组件、Story Q&A 等渲染成本观测；
- 后端事件上报、远端日志和持久化；
- 一键复制或导出 JSON；
- 比赛现场或生产环境中的临时诊断入口；
- 完整性能分析平台或跨设备 tracing；
- 自动给出卡顿原因或优化建议。

## 4. 方案选择

### 4.1 采用方案

采用集中式内存观测器和结构化事件。

`PlayerFeed`、`PlayerPage` 和 `VideoStage` 只负责上报与自身职责相关的事实事件；观测器负责：

- 保存最近事件；
- 去重无价值的重复状态；
- 维护已挂载页面和播放器状态摘要；
- 计算活动页切换耗时；
- 输出统一格式的终端日志；
- 为屏幕内 Debug 浮层提供快照。

### 4.2 未采用方案

未采用在组件中直接散落 `console.log` 的方式，因为它无法稳定计算耗时，也难以支持屏幕内摘要。

未采用远端性能分析或后端上报，因为当前阶段需要先定位端内 Feed 和播放器问题，远端链路会扩大范围并混入业务事件系统。

## 5. 启用边界

观测器只在同时满足以下条件时启用：

```text
__DEV__ === true
mode === "home"
```

当条件不满足时：

- 不创建 Home Feed 观测状态；
- 不显示 Debug 按钮；
- 不输出 Home Feed 播放日志；
- 不要求 Series Feed 或广告页传入观测参数。

该观测能力是开发旁路能力，不进入后端 `User Event` 契约。

## 6. 架构

```text
PlayerFeed
  ├─ feed_scroll_begin / feed_scroll_end
  ├─ feed_active_item_change
  ├─ page_mount / page_unmount
  └─ preload_state_change
       │
PlayerPage
  └─ playback_ownership_change
       │
VideoStage
  ├─ player_create / player_release
  ├─ status_change / source_load
  ├─ play_command / pause_command
  ├─ playing_change
  └─ first_frame_render
       │
       ▼
HomeFeedPlaybackObserver
  ├─ 内存事件缓冲区
  ├─ 页面与播放器状态摘要
  ├─ 切换耗时计算
  └─ 统一终端 JSON 日志
       │
       ▼
Home Feed 右上角 Debug 按钮与浮层
```

### 6.1 组件职责

#### `PlayerFeed`

负责上报 Feed 级事实：

- Home Feed 初始化时认定的首个活动项；
- 用户开始和结束一次竖滑；
- Feed 认定新的活动项；
- Feed 页挂载或卸载；
- 页面是否进入相邻预加载窗口。

#### `PlayerPage`

负责上报页面是否拥有播放权。播放权由当前 `isActive` 和用户播放意图共同决定。

#### `VideoStage`

负责上报 `expo-video` 相关事实：

- player 创建和释放；
- player 状态变化；
- source 加载完成；
- 应用发出的播放或暂停命令；
- native player 的真实播放状态变化；
- player 的静音状态变化；
- `VideoView.onFirstFrameRender` 首帧渲染。

#### `HomeFeedPlaybackObserver`

负责接收事件、生成事件序号和相对时间、维护内存状态、计算指标并输出日志。它不直接访问或控制 `VideoPlayer`。

#### `HomeFeedPlaybackDebugPanel`

负责展示观测器快照。它只读取观测状态，不控制 Feed 或播放器。

## 7. 事件模型

每条事件使用统一结构：

```ts
interface HomeFeedPlaybackEvent {
  sequence: number;
  timestampMs: number;
  elapsedMs: number;
  eventType: HomeFeedPlaybackEventType;
  videoId?: string;
  pageIndex?: number;
  activeIndex?: number;
  details?: Record<string, string | number | boolean | undefined>;
}
```

其中：

- `sequence`：本次运行中的递增序号，用于稳定排序；
- `timestampMs`：事件发生时的绝对毫秒时间；
- `elapsedMs`：相对观测器创建时刻的毫秒时间；
- `eventType`：结构化事件类型；
- `videoId`：与具体视频相关时填写；
- `pageIndex`：与具体 Feed 页相关时填写；
- `activeIndex`：事件发生时已知的活动页索引；
- `details`：事件特有的轻量字段。

### 7.1 Feed 事件

- `feed_scroll_begin`
- `feed_scroll_end`
- `feed_active_item_change`

### 7.2 页面事件

- `page_mount`
- `page_unmount`
- `preload_state_change`
- `playback_ownership_change`

### 7.3 Player 事件

- `player_create`
- `player_release`
- `status_change`
- `source_load`
- `play_command`
- `pause_command`
- `playing_change`
- `muted_change`
- `first_frame_render`

### 7.4 不采集的高频事件

第一版不记录每次 `timeUpdate`。高频进度事件会放大日志量，并可能让观测工具本身影响播放器性能。

## 8. 状态摘要与指标

观测器维护每个已知页面的摘要：

```ts
interface HomeFeedPlaybackPageSnapshot {
  videoId: string;
  pageIndex: number;
  isMounted: boolean;
  isPreloaded: boolean;
  hasPlaybackOwnership: boolean;
  playerStatus?: string;
  isPlaying?: boolean;
  isMuted?: boolean;
}
```

观测器维护最近一次活动页切换指标：

```ts
interface HomeFeedPlaybackSwitchMetrics {
  videoId: string;
  pageIndex: number;
  activeChangedAtMs: number;
  playingLatencyMs?: number;
  firstFrameLatencyMs?: number;
}
```

计算规则：

- `feed_active_item_change` 创建一次新的切换指标；
- Home Feed 初始化时也上报一次 `feed_active_item_change`，用于计算首屏指标；
- 该视频切换后的第一个 `playing_change` 且 `isPlaying === true` 计算 `playingLatencyMs`；
- 该视频切换后的第一个 `first_frame_render` 计算 `firstFrameLatencyMs`；
- 后续相同视频的首帧事件可以继续进入事件流，但不覆盖同一次切换的首帧耗时；
- 如果目标视频已经预加载并提前渲染过首帧，切换后仍以切换后的首个首帧事件为准；若没有新的首帧事件，则指标保持未定义，避免伪造耗时。

## 9. 终端日志

每条事件使用统一前缀输出：

```text
[HomeFeedPlayback] {"sequence":12,"eventType":"playing_change",...}
```

日志要求：

- 输出完整结构化事件；
- 保持单行 JSON，方便搜索和后续脚本处理；
- 仅开发模式 Home Feed 输出；
- 日志失败不得影响观测器状态和播放器行为。

## 10. 屏幕内 Debug 面板

### 10.1 入口

Home Feed 右上角增加一个仅开发模式可见的 Debug 按钮。

采用“右上角开关 + 浮层”布局：

- 默认关闭，尽量不干扰正常观看；
- 点击后展开浮层；
- 再次点击关闭；
- 面板关闭时仍继续采集，以便卡顿发生后再打开查看。

### 10.2 展示内容

浮层只展示高信号摘要：

- 当前 `activeIndex` 和 `videoId`；
- 当前页和相邻已挂载页的 `mounted`、`preloaded`、`status`、`playing`、`muted`；
- 最近一次切换的 `active change → playing` 耗时；
- 最近一次切换的 `active change → first frame` 耗时；
- 最近 6 条事件；
- “清空”按钮。

完整事件仍以终端日志为准，浮层不承担完整时间线展示职责。

## 11. 内存与去重策略

- 事件缓冲区最多保留最近 200 条；
- 超出上限时移除最早事件；
- 清空操作会清除事件、页面摘要和切换指标；
- 对相同目标、相同状态的连续状态事件去重；
- 不对有独立时序价值的命令事件强制去重；
- 观测器生命周期与 Home Feed 生命周期一致，不持久化到下一次应用启动。

## 12. 错误处理与性能约束

- 观测器是旁路能力，任何异常都不能阻断 Feed 滑动和视频播放；
- 面板只读取快照，不直接控制 player；
- `player_release` 在清理阶段记录，记录后不得再次读取已释放 player 属性；
- 不记录高频 `timeUpdate`；
- 不在生产环境创建观测状态或渲染面板；
- 不把观测事件混入业务行为事件或后端接口；
- 首帧使用 `VideoView.onFirstFrameRender`，不使用 `timeUpdate` 近似。

## 13. 测试策略

自动测试优先覆盖纯逻辑观测器：

1. 事件缓冲区最多保留 200 条；
2. 相同状态事件去重；
3. 活动页切换后正确计算 `playingLatencyMs`；
4. 活动页切换后正确计算 `firstFrameLatencyMs`；
5. 后续首帧不会覆盖同一次切换指标；
6. 清空后事件、页面摘要和切换指标归零。

项目验证包括：

```bash
cd apps/player-demo
npm run typecheck
npm test
git diff --check
```

真机 Smoke Check 建议观察：

1. Home Feed 右上角仅开发模式出现 Debug 按钮；
2. 面板关闭时滑动，打开后仍能看到最近事件；
3. 从 ep01 滑到 ep02 时，终端能看到活动页变化、播放命令、真实播放状态和首帧事件；
4. 相邻预加载页不应显示为实际播放；
5. Series Feed 不显示 Home Feed Debug 按钮，也不输出 Home Feed 播放日志。

## 14. 文档影响

实现后需要同步更新：

- `docs/develop-docs/module-designs/mobile-player-demo.md`
- `docs/develop-docs/status/current-implementation.md`

文档应说明 Home Feed 已具备仅开发模式的播放观测工具，以及它不属于普通用户界面和业务事件链路。

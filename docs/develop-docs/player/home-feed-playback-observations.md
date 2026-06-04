# Home Feed 视频播放与竖滑 Feed 真机观测结论

## 1. 背景

当前播放器优化主线先聚焦 Home Feed，不处理广告页和 Series Feed 的特殊行为。

在真机体验中曾观察到两个明显问题：

- 用户停留在当前剧集时，偶尔能听到后续剧集的声音；
- 用户向后滑回已经看过的剧集时，会先看到视频开头画面短暂卡住，然后才跳到应当恢复的播放位置。

为避免只凭体感判断，前端增加了开发模式下的 Home Feed 播放观测能力，记录 Feed、页面和 `expo-video` player 的关键事件。本次结论基于 2026 年 6 月 4 日的一次真机日志 `ob.log`。原始日志是本地调试产物，不提交到仓库。

## 2. 观测范围

本次日志覆盖：

- Home Feed 首屏冷启动；
- 从第 1 页连续向前滑到第 4 页；
- 再从第 4 页连续向后滑回第 1 页；
- 相邻页预加载；
- 超出预加载窗口后的 player 回收与重建；
- 应用发出的播放、暂停命令和 native player 的真实播放状态。

本次日志不覆盖：

- Series Feed；
- 广告页；
- 网络视频源；
- seek 请求与 seek 完成的精确时间；
- 目标恢复帧真正显示出来的精确时间。

## 3. 结论摘要

1. 非活动的预加载 player 确实会在没有应用层 `play_command` 的情况下短暂进入播放状态。当前的静音和补偿暂停已经消除了串音，但仍未阻止后台 player 启动解码和推进。
2. Feed 只在 `onMomentumScrollEnd` 后切换活动页。一次滑动开始到活动页切换约需 `1.1` 至 `1.27` 秒，在此期间旧页仍拥有播放权。
3. 对已完成预加载的前向目标页，首帧通常在页面激活前已经渲染。前向切换的主要等待不是首帧解码，而是活动页切换、React effect 执行和 native player 真正开始播放之间的时序。
4. 反向滑回旧集时的明显卡顿，主要是恢复播放生命周期和 seek 顺序问题，不是本地文件读取慢：旧 player 被回收后，新 player 先渲染了视频开头帧，页面激活后又先播放，再恢复到已保存进度。
5. 首屏冷启动约需 `2.3` 秒才真正播放，约需 `2.7` 秒才渲染首帧。这是独立于 Feed 切换的优化问题。

## 4. 详细观察

### 4.1 非活动预加载 player 会意外进入播放

以第 2 集为例：

```text
ob.log:15  playback_ownership_change hasPlaybackOwnership=false
ob.log:19  status_change status=readyToPlay
ob.log:20  playing_change isPlaying=true
ob.log:21  pause_command reason=unexpected_playing_state
ob.log:22  playing_change isPlaying=false
```

第 2 集没有播放权，也没有在 `ob.log:20` 之前收到应用层 `play_command`，但 native player 仍进入了播放状态。相同模式也出现在：

- 第 3 集：`ob.log:49` 至 `ob.log:54`
- `beiwang_ep07`：`ob.log:79` 至 `ob.log:84`
- `beiwang_ep08`：`ob.log:110` 至 `ob.log:115`
- 重建后的第 2 集：`ob.log:138` 至 `ob.log:141`
- 重建后的第 1 集：`ob.log:167` 至 `ob.log:172`

当前保护逻辑会让非活动页保持静音，并在检测到意外播放后立即暂停。日志中的意外播放持续时间如下：

| 视频 | 检测到意外播放后停止耗时 |
| --- | ---: |
| `beipai_xunbao_biji_ep02` | 17 ms |
| `beipai_xunbao_biji_ep03` | 73 ms |
| `beiwang_ep07` | 99 ms |
| `beiwang_ep08` | 154 ms |
| 重建后的 `beipai_xunbao_biji_ep02` | 19 ms |
| 重建后的 `beipai_xunbao_biji_ep01` | 47 ms |

**结论：** 当前已经解决“用户能听到后台声音”的表象，但“先播放、再纠正”不等于“没有播放”。后台 player 仍可能消耗解码资源，也解释了之前后续剧集或广告在切入前已经播放了一段时间的现象。

由于所有应用层 `player.play()` 调用都已记录为 `play_command`，意外播放很可能发生在 `expo-video` 或 native player 的资源就绪流程中。这是基于日志的推断，尚未定位到 `expo-video` 内部的具体根因。

### 4.2 Feed 在滑动结束后才切换播放权

`PlayerFeed` 当前通过 `onMomentumScrollEnd` 更新活动页。真机日志中，每次从开始滑动到活动页切换的耗时如下：

| 切换 | 滑动耗时 |
| --- | ---: |
| 第 1 页 -> 第 2 页 | 1135 ms |
| 第 2 页 -> 第 3 页 | 1182 ms |
| 第 3 页 -> 第 4 页 | 1110 ms |
| 第 4 页 -> 第 3 页 | 1272 ms |
| 第 3 页 -> 第 2 页 | 1099 ms |
| 第 2 页 -> 第 1 页 | 1148 ms |

例如，第 1 页到第 2 页的事件顺序为：

```text
ob.log:27  feed_scroll_begin activeIndex=0
ob.log:31  feed_scroll_end activeIndex=0
ob.log:32  feed_active_item_change activeIndex=1
```

**结论：** 用户手指拖动和 Feed 惯性滚动期间，旧页仍是活动页并继续拥有播放权。这个行为是否需要提前切换，仍需要结合实际手感评估；当前不能直接判定它是错误，但它会影响用户对切换响应速度的感知。

### 4.3 活动页确认后，真正播放仍有额外延迟

活动页变化后，应用发出 `play_command`，native player 再进入 `playing=true`。本次日志中的耗时如下：

| 目标页 | 活动页变化 -> `play_command` | 活动页变化 -> `playing=true` |
| --- | ---: | ---: |
| 第 2 页 | 104 ms | 234 ms |
| 第 3 页 | 154 ms | 281 ms |
| 第 4 页 | 129 ms | 259 ms |
| 返回第 3 页 | 140 ms | 360 ms |
| 返回第 2 页 | 117 ms | 278 ms |
| 返回第 1 页 | 73 ms | 247 ms |

对应事件示例：

```text
ob.log:32  feed_active_item_change videoId=beipai_xunbao_biji_ep02
ob.log:37  play_command videoId=beipai_xunbao_biji_ep02
ob.log:48  playing_change isPlaying=true videoId=beipai_xunbao_biji_ep02
```

**结论：** Feed 确认新活动页后，还有约 `234` 至 `360` 毫秒的播放权传递和 native 播放启动延迟。这段延迟是切换卡顿的重要组成部分。

### 4.4 前向滑动目标页通常已经有首帧

前向滑动时，相邻目标页已经在预加载窗口内，并且在成为活动页之前渲染了首帧：

```text
ob.log:24  第 2 集 first_frame_render
ob.log:32  第 2 集 feed_active_item_change

ob.log:52  第 3 集 first_frame_render
ob.log:60  第 3 集 feed_active_item_change

ob.log:83  beiwang_ep07 first_frame_render
ob.log:90  beiwang_ep07 feed_active_item_change
```

**结论：** 对这些前向切换，目标页的视觉首帧已经准备好。主要等待发生在活动页变化和真正播放之间，而不是首次解码目标页首帧。

当前“活动页变化 -> 首帧”指标在页面提前渲染首帧时会保持未定义。后续观测应明确区分：

- 目标页在激活前已经有首帧；
- 目标页激活后才首次渲染首帧。

### 4.5 反向滑回旧集时的卡顿来自 player 重建和恢复 seek

当前预加载距离为 `1`，只有活动页和前后相邻页保留视频 player。用户到达第 4 页时，第 2 集超出预加载窗口并被释放：

```text
ob.log:90  第 4 页成为活动页
ob.log:91  第 2 集 player_release
```

用户返回第 3 页后，第 2 集重新进入相邻预加载窗口并创建新 player：

```text
ob.log:118  第 3 页成为活动页
ob.log:120  第 2 集 player_create
ob.log:142  第 2 集 first_frame_render
```

此时第 2 集尚未成为活动页，新 player 已经渲染了视频开头帧。继续滑回第 2 集后：

```text
ob.log:146  第 2 集 feed_active_item_change
ob.log:154  第 2 集 play_command
ob.log:164  第 2 集 playing_change isPlaying=true
```

代码时序也支持这一解释：

- `PlayerPage` 只在页面成为活动页时，根据 `initialPlaybackTime` 创建恢复进度的 `seekRequest`；
- `VideoStage` 中播放状态协调 effect 声明在 seek effect 之前；
- 因此活动状态和 `seekRequest` 同时更新时，可能先执行 `play()`，再设置 `player.currentTime`；
- 设置 `currentTime` 需要解码目标位置附近的帧，期间页面会继续显示已经渲染的开头帧。

综合日志和代码，当前可解释为：

```text
旧 player 超出预加载窗口后被释放
-> 返回时创建新 player
-> 新 player 先渲染 0 秒附近的开头帧
-> 页面成为活动页
-> play() 先启动
-> 恢复进度 seek 随后执行
-> 目标位置帧完成解码
-> 画面从开头帧跳到已保存进度
```

**结论：** 用户看到的“开头画面卡一下，再跳回 10 秒附近”主要是恢复播放生命周期和 seek 顺序问题，不是本地视频文件仍然存在网络式加载延迟。

本次日志尚未记录 `seekRequest` 和目标恢复帧显示时间，因此上述最后几步是高可信推断，仍需要新增 seek 事件后精确验证。

### 4.6 首屏冷启动是独立问题

首屏第 1 集的关键事件为：

```text
ob.log:16  feed_active_item_change
ob.log:17  status_change status=readyToPlay
ob.log:18  playing_change isPlaying=true
ob.log:23  first_frame_render
```

相对活动页确认时间：

- `readyToPlay`：约 `2207` ms；
- `playing=true`：约 `2321` ms；
- 首帧渲染：约 `2726` ms。

**结论：** 首屏冷启动明显慢于已预加载页面切换，应作为独立优化课题处理，不能与反向恢复进度问题混在一起。

## 5. 已确认事实、推断与待验证项

### 5.1 已确认事实

- 非活动预加载 player 会在没有应用层 `play_command` 的情况下进入 `playing=true`；
- 当前静音和补偿暂停逻辑能阻止用户继续听到后台声音；
- player 会根据预加载距离被释放和重建；
- 重建后的旧集会在成为活动页前渲染首帧；
- 恢复进度的 `seekRequest` 只在页面成为活动页后生成；
- `VideoStage` 的播放状态协调 effect 声明在 seek effect 之前；
- Feed 只在 `onMomentumScrollEnd` 后更新活动页。

### 5.2 高可信推断

- 非活动 player 的意外播放来自 `expo-video` 或 native player 的资源就绪流程；
- 反向滑回旧集时的开头帧卡顿，来自“先渲染开头帧、再播放、再 seek、再解码目标帧”的时序。

### 5.3 尚未测量

- 日志中每次恢复使用的具体保存进度；
- `seekRequest` 创建、设置 `currentTime` 和 seek 生效的精确时间；
- 恢复位置目标帧真正显示出来的时间；
- 提前于 `onMomentumScrollEnd` 切换播放权是否会改善整体手感；
- 完全阻止非活动 player 启动播放的可靠方式。

## 6. 优化优先级

### P0：修复反向恢复进度时序

1. 新建或重建预加载 player 时，尽早初始化到已保存播放位置，不要等页面成为活动页才创建恢复 seek。
2. 页面激活时，应保证恢复 seek 先于 `play()` 执行。
3. 必要时在目标位置帧准备好之前保留占位画面或延迟播放，避免展示错误的开头帧。

### P0 实现方向更新

2026 年 6 月 4 日的前端调整不再直接围绕 `isActive` 打补丁，而是先把 Feed 播放编排拆成更明确的页面状态：

- `active`：当前拥有播放权的页面；
- `preload`：相邻预加载页面，应创建并准备 video player，但不拥有播放权；
- `parked`：超出预加载窗口的页面，不应保留 video player。

`PlayerFeed` 通过前端 domain coordinator 统一计算页面角色、是否准备 video player、是否拥有播放权和恢复播放时间。`PlayerPage` 消费 coordinator 给出的 `resumeTime`，不再等页面成为 active 后才为恢复进度创建 seek。`VideoStage` 支持在 player 创建时初始化恢复位置，并在存在待处理 seek 时阻塞 `play()` 命令，避免同一轮状态更新中出现“先播放、后 seek”。

新增的 Home Feed 播放观测事件：

- `resume_position_initialized`：player 创建时尝试初始化到保存进度；
- `seek_requested`：组件收到 seek 请求；
- `seek_applied`：已向 native player 设置 `currentTime`。

### P1：阻止非活动 player 真正进入播放

当前方案是在检测到意外播放后暂停。下一步应验证能否在 player 创建、source 加载或预加载配置层面阻止非活动 player 启动，而不是依赖事后纠正。

### P1：缩短活动页变化后的播放启动延迟

重点拆分并测量：

- `feed_active_item_change -> play_command`；
- `play_command -> playing=true`；
- React render、effect 和 native player 各自的耗时。

### P2：评估播放权切换时机

验证是否需要在页面可见比例达到阈值时提前切换播放权，而不是只依赖 `onMomentumScrollEnd`。该改动会影响滑动中回弹、快速连续滑动和声音切换，需要单独评估。

2026 年 6 月 4 日的下一版实现选择了更接近短视频 App 手感的折中方案：拖动过程中不切播放权，用户松手时通过 `onScrollEndDrag` 预测最终吸附页，并提前把 `playbackOwnerIndex` 交给目标页；`onMomentumScrollEnd` 只负责最终校准 `settledIndex` 和播放权。预测优先使用 native `targetContentOffset`，没有该字段时使用松手时的 `velocityY` 和当前 offset fallback。这样可以避免用户手指拖动时声音/播放来回切，又能减少“下一页首帧已出现但要等惯性滚动结束才播放”的停顿。

新增观测事件：

- `feed_scroll_release`：用户松手，记录当前 offset、预测目标页和 native `targetContentOffset`；
- `feed_playback_owner_change`：播放权切换，作为 release 后播放启动延迟的指标起点。

### P2：优化首屏冷启动

首屏 source 加载、player 就绪和首帧渲染需要单独建立基线并优化。

## 7. 下一轮观测需求

为验证恢复播放修复，应补充以下事件：

- `seek_requested`：记录请求时间、目标时间和触发原因；已接入前端观测；
- `seek_applied`：记录设置 `player.currentTime` 的时间；已接入前端观测；
- `resume_position_initialized`：记录预加载 player 是否已初始化到保存进度；已接入前端观测；
- seek 后第一次有效 `timeUpdate` 或目标帧准备完成事件；
- 页面激活前是否已经渲染首帧的明确状态。

下一轮真机验证至少应覆盖：

1. 第 2 集播放到约 10 秒；
2. 向前滑到第 4 页，使第 2 集 player 被释放；
3. 向后滑回第 2 集；
4. 确认不再显示开头帧后跳转；
5. 确认非活动页没有进入 `playing=true`；
6. 对比修复前后的活动页变化、seek 和真正播放耗时。

## 8. 相关文档

- `docs/superpowers/specs/2026-06-04-home-feed-playback-observability-design.md`
- `docs/develop-docs/player/player-vertical-swipe-requirements.md`
- `docs/develop-docs/module-designs/mobile-player-demo.md`

# Home Feed 视频传输、缓存与未解决问题

## 1. 背景

本文记录 Home Feed 播放优化中关于视频传输、客户端缓存和预缓冲机制的当前判断。

截至 2026 年 6 月 5 日，Home Feed 已经解决中速滑动下的主要体验问题：

- 前向切换时，相邻页能提前渲染首帧；
- active 页使用更稳的 buffer 策略，减少“首帧出来后播 1 秒就卡住”；
- 反向滑回旧集时，能够从原本停留位置恢复播放；
- `visualActiveIndex`、`playbackOwnerIndex` 和 `activeIndex` 已拆开，避免完整 UI 和视频播放在同一帧突兀启动。

但快速连续滑动仍无法达到抖音级跟手感。当前判断是：这已经不是单纯的 React UI 或 `bufferOptions` 问题，而是缺少更底层的 byte cache、预取调度和播放器资源复用。

## 2. 当前实现状态

### 2.1 视频来源

当前比赛 Demo 仍主要使用本地或后端提供的短剧 mp4 视频。前端通过 `streamUrl` 交给 `expo-video` 播放。

后续云端部署计划中，视频传输会走 CDN。CDN 能改善：

- 首字节响应时间；
- Range 请求稳定性；
- 服务端压力；
- 热门视频在边缘节点的命中率；
- 云端带宽和并发能力。

但 CDN 不能替代客户端预缓冲。短视频 Feed 需要解决的是：

```text
用户滑到某个视频前，客户端是否已经拿到可播放的前几秒字节
```

### 2.2 客户端播放器

当前移动端使用 React Native + Expo + `expo-video`。

Home Feed 通过页面角色控制 player 生命周期：

- `active`：当前拥有播放权，渲染完整 UI，执行 `play()`；
- `preload`：相邻预加载页，保留静音 `VideoStage`，准备 player 和首帧，但不拥有播放权；
- `parked`：超出预加载窗口，不挂载 video player。

视频离开预加载窗口后，`VideoStage` 会卸载，native player 会释放。对应的解码状态、内存 buffer 和 player 内部已读数据不能假设继续保留。

### 2.3 bufferOptions

当前已经启用 `expo-video` 的 `bufferOptions`，并区分 active 与 preload：

```text
active:
  preferredForwardBufferDuration: 18
  minBufferForPlayback: 2.5
  maxBufferBytes: 48MB
  waitsToMinimizeStalling: true

preload:
  preferredForwardBufferDuration: 8
  minBufferForPlayback: 1
  maxBufferBytes: 24MB
  waitsToMinimizeStalling: false
```

注意：不同平台对这些字段的支持不完全相同。iOS 上主要依赖 `preferredForwardBufferDuration` 和 `waitsToMinimizeStalling`；部分更偏 Android 的 buffer 字段不能作为 iOS 真机效果的唯一依据。

### 2.4 source caching

`expo-video` 的 `VideoSource.useCaching` 当前默认关闭：

```text
FEED_VIDEO_SOURCE_CACHING_ENABLED = false
```

关闭原因不是忘记开启，而是之前 iOS 真机实验中，打开 source caching 后部分 progressive mp4 视频进入过：

```text
status=error
Operation Stopped
source_load duration=null
```

因此当前稳定版本选择禁用 source caching，优先保证资源可播放。

`buildVideoStageSource` 仍保留按需包装 `useCaching: true` 的能力。后续可以重新进行受控实验，尤其是在云端 CDN、响应头和视频文件结构更稳定后。

## 3. CDN 与 HLS 的判断

### 3.1 Progressive MP4 + CDN

Progressive MP4 + CDN 的优点是简单、调试直接，并且更适合在 Expo 层实验 `useCaching`。

需要确认 CDN 和源站支持：

- `Accept-Ranges: bytes`；
- `206 Partial Content`；
- 正确的 `Content-Length`；
- 正确的 `Content-Type: video/mp4`；
- mp4 `moov atom` 前置。

对于比赛 Demo，这条路线的投入产出比最高：

```text
CDN + progressive mp4 + expo-video bufferOptions + 可选 useCaching 实验
```

### 3.2 HLS + CDN

HLS 把视频拆成 playlist 和多个 segment：

```text
master.m3u8
-> variant playlist
-> segment1.ts / segment2.ts / .m4s
```

HLS 对云端传输更生产化，优点包括：

- CDN 更容易缓存小分片；
- 支持多码率自适应；
- 对网络波动更稳；
- 不强依赖 mp4 Range 请求。

但 HLS 不等于客户端 feed 缓存。`expo-video` 的 `useCaching` 对 HLS，尤其 iOS，并不能作为稳定可控的持久缓存方案。iOS 的 AVPlayer 可能会有系统级缓存或内存 buffer，但这不是业务层可调度的“预取后几秒字节”。

如果未来使用 HLS，需要重点控制切片参数：

- segment 时长建议 1 至 2 秒；
- keyframe 对齐 segment 边界；
- 使用 independent segments；
- 控制码率，避免首段过大；
- CDN 缓存 playlist 和 segment。

对当前比赛 Demo 来说，HLS 更适合展示云端传输规范化，不适合作为客户端快速滑动跟手感的唯一解决方案。

## 4. 与开源短视频项目的差距

仓库中参考了两个开源项目：

- `docs/references/flutter_tiktok`
- `docs/references/YCScrollPager`

### 4.1 flutter_tiktok

Flutter 项目主要使用 `video_player` 做组件级预加载。

它的机制包括：

- `PageView` 竖滑；
- 相邻视频 `initialize()`；
- 当前视频 `play()`；
- 旧视频 `pause()` 或 `dispose()`。

它没有显式 byte cache，也没有播放器池。代码中还注明 Android 侧 `VideoPlayer` 有问题，`disposeCount` 只能设为 0，否则第三个开始的视频可能无法加载。

因此该项目更像 UI Demo，不具备抖音级快速连续滑动能力。

### 4.2 YCScrollPager

Android 项目更有参考价值。它的 `TikTok2Activity` 和 `Tiktok2Adapter` 采用了：

- `PreloadManager.addPreloadTask(url, position)`；
- `mPreloadManager.getPlayUrl(originalUrl)`；
- `ProxyVideoCacheManager`；
- `VideoCache` 依赖；
- 封面图占位；
- `ViewPager.setOffscreenPageLimit(4)`；
- 单个 `VideoPlayer` 在页面 container 之间移动；
- 滚动中暂停 preload，滚动停止后恢复 preload。

其核心不是“同时养很多播放器”，而是：

```text
原始 URL
-> PreloadManager 提前下载字节
-> ProxyVideoCacheManager 返回本地代理 URL
-> VideoPlayer 播放代理 URL
```

这比当前 Expo 实现更接近短视频 App 的传输和缓存模型。

但它也不是完整抖音级实现：

- 切页时仍会 release 当前 `VideoPlayer` 并重新 setUrl/start；
- 没看到回滑恢复原播放位置；
- 没有复杂推荐预测、多码率策略或生产级播放器池；
- demo 中 `onDestroy` 会清缓存，虽然注释说明实际使用可不清。

## 5. 已解决的问题

### 5.1 中速前向切换

相邻页预加载、active buffer 分档和播放权提前切换已经能支持用户每 3 秒滑一集的顺畅体验。

### 5.2 反向回滑恢复

当前实现已经支持：

```text
滑走视频
-> 超出预加载窗口后 player release
-> 回滑重新进入窗口
-> 新 player 初始化到保存进度
-> 页面激活后从原停留位置播放
```

这解决了“回滑先看到 0 秒画面，再跳回原位置”的主要问题。

### 5.3 UI 与播放启动解耦

当前 Feed 使用三层状态：

- `visualActiveIndex`：负责视觉页和完整 UI；
- `playbackOwnerIndex`：负责真正播放；
- `activeIndex`：负责 settled 页和对外上报。

这解决了“首帧先出现，随后 UI 和视频同时启动”的突兀感。

## 6. 仍未解决的问题

### 6.1 快速连续滑动仍不具备抖音级跟手感

当前方案在中速滑动下已经可用，但用户快速连续下滑时，每个新视频能获得的预热时间很短。

根因是当前预热仍依赖 video player 生命周期：

```text
相邻页挂载 VideoStage
-> native player 准备 source 和首帧
```

而不是独立的 byte preload manager：

```text
Feed 预测后续视频
-> 下载前几秒字节
-> 写入磁盘或内存 cache
-> player 切换时直接读 cache
```

### 6.2 没有稳定的跨 player 缓存

视频离开预加载窗口后 player 会释放。当前没有自研本地 proxy cache，也没有默认启用 `expo-video` source caching。

因此 player 被释放后，后续再创建 player 需要重新准备视频资源。

### 6.3 未验证云端 CDN 下的 useCaching

本地或当前后端环境中，`useCaching` 曾导致 iOS 加载错误。但这不代表云端 CDN 场景下一定不可用。

后续需要在 CDN 环境下重新验证：

- progressive mp4；
- 正确响应头；
- Range 请求；
- 不同视频文件；
- iOS Expo Go 或 Dev Client。

### 6.4 HLS 无法直接替代客户端预取

HLS 能改善云端传输稳定性，但不能自动让客户端在快速滑动前拿到后续视频的前几秒。

如果使用 HLS，还需要额外设计 segment 级预取或依赖 native 播放器内部策略。Expo 层目前不适合把 HLS 当成可控 byte cache。

### 6.5 Expo Go 限制

在 Expo Go 中，能控制的是：

- `expo-video` player 生命周期；
- `bufferOptions`；
- `VideoSource.useCaching`；
- React Native 组件挂载与渲染；
- Feed 层预加载窗口。

难以直接实现的是：

- 自定义 native player pool；
- 自定义 AVPlayer/ExoPlayer cache；
- 本地代理 cache server；
- segment 级预取调度；
- 渲染 surface 复用。

如果后续要继续逼近短视频 App 手感，需要评估 Expo Dev Client 或原生模块。

## 7. 后续建议

### 7.1 比赛 Demo 优先路线

建议优先走低复杂度路线：

```text
progressive mp4
+ CDN
+ 正确 Range/Content-Type/moov 前置
+ 当前 feed 预加载机制
+ active/preload buffer 分档
+ 受控实验 expo-video useCaching
```

这条路线最适合比赛 Demo，工程风险低，且能继续提升快速滑动体验。

### 7.2 useCaching 受控实验

建议新增一个可开关配置，而不是直接长期打开：

```text
EXPO_PUBLIC_FEED_VIDEO_SOURCE_CACHING_ENABLED=true
```

实验时必须保留日志：

- `source_load.duration`；
- `status_change.error`；
- `buffer_health.bufferAhead`；
- `first_frame_render`；
- `feed_playback_owner_change -> playing=true` 延迟。

如果再次出现 `Operation Stopped` 或 `duration=null`，应立即回滚到关闭状态。

### 7.3 中期路线

如果比赛 Demo 后仍继续优化，可考虑：

1. 引入 Expo Dev Client；
2. 评估原生 cache 或本地 proxy preload；
3. 把预加载从“创建下一个 player”升级为“提前下载字节”；
4. 支持根据滑动速度动态预取 `i+1/i+2/i+3`；
5. 为 feed 视频增加封面图或首帧图，作为播放器未就绪时的视觉兜底。

## 8. 当前结论

当前 Home Feed 已经达到比赛 Demo 可接受的中速滑动体验，但尚未达到抖音级快速连续滑动体验。

差距主要在：

```text
显式 byte cache
+ 预取调度
+ 播放器资源复用
+ 视频封装/切片优化
+ 原生级滚动播放协同
```

在比赛 Demo 范围内，下一步最值得尝试的是：

```text
云端 CDN 环境下，重新受控验证 expo-video useCaching
```

如果该能力稳定可用，它会是当前 Expo 架构下最接近开源 Android 项目 `ProxyVideoCacheManager` 的低成本方案。

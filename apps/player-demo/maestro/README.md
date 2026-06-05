# Maestro UI Smoke Flows

这组 flow 用于在 iOS Simulator 的 DramePulse development build 中快速检查播放器 Demo 的关键页面，并产出截图。

## 前置条件

1. 安装并启动 DramePulse development build：

```bash
cd apps/player-demo
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run ios:dev-build
```

2. 启动 dev client 的 Metro server：

```bash
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run start:dev-client -- --clear
```

当前 development build 的 iOS app id 是：

```text
com.dramepulse.playerdemo
```

Maestro 会直接启动 DramePulse App，而不是启动 Expo Go，因此可以使用默认 `launchApp` 重启 App，状态比 Expo Go 稳定。

## 运行

从 Maestro flow 所在 worktree 根目录执行：

```bash
maestro test apps/player-demo/maestro/ios/home.yaml
maestro test apps/player-demo/maestro/ios/theater.yaml
maestro test apps/player-demo/maestro/ios/series-player.yaml
```

也可以一次运行整个目录：

```bash
maestro test apps/player-demo/maestro/ios
```

## Flow 覆盖

- `home.yaml`：启动 App，等待首页加载，截图首页。
- `theater.yaml`：从首页进入剧场页，等待搜索框出现，截图剧场页。
- `series-player.yaml`：从剧场页点第一张剧卡进入播放页，打开选集面板，截图播放页/选集状态。

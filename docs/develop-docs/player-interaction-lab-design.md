# 播放器交互方式实验台设计说明

## 1. 背景

比赛重点之一是短剧播放过程中的即时互动方式。当前播放器已经具备真实视频播放、弹幕展示和基础播放控制能力，下一步需要让前端开发人员可以快速尝试不同的互动呈现形式。

本设计只服务开发阶段的 UI 试验，不代表最终给评委展示的正式方案。最终展示时应只保留一个确定的互动方案，不暴露切换控件。

## 2. 目标

在 `apps/player-demo` 中增加一个前端本地的 Interaction Lab，用于横向比较不同交互 UI 的手感和视觉效果。

第一版目标：

1. 提供一个开发用控制入口，可以切换互动呈现方式；
2. 固定同一个视频时间点和同一个问题；
3. 支持 `poll_bar` 和 `emoji_hold` 两种 UI example；
4. 纯前端演示，不从后端获取 interaction plan；
5. 不记录用户事件，不做统计，不回传后端；
6. 不影响现有视频播放、进度条、弹幕和后端数据加载。

## 3. 非目标

第一版不做：

- 不接入后端 `Interaction Plan`；
- 不接入 `POST /api/playback-events`；
- 不做用户事件统计；
- 不做策略更新；
- 不做高光点识别联动；
- 不做复杂配置后台；
- 不做 `quick_reaction` 等更多实验形态。

## 4. 开发模式与正式模式

Interaction Lab 是开发工具，不是正式播放器功能。

开发模式：

- 显示一个轻量控制入口；
- 可以切换 `Off`、`Poll Bar`、`Emoji Hold`；
- 选中后立即影响当前播放器的互动 UI；
- 用于开发人员和产品同学快速比较不同方案。

正式模式：

- 不显示 Interaction Lab 控制入口；
- 只展示最终选定的一种互动方式；
- 不暴露调试控件和 example 列表。

建议增加一个前端配置开关：

```ts
export const ENABLE_INTERACTION_LAB = true;
```

后续准备正式演示时，可以将其改为 `false`，或者改成环境变量控制。

## 5. 固定实验内容

第一版只比较 UI 呈现方式，不比较不同互动文案或触发策略。

固定内容建议：

```text
triggerTimeSec = 8
prompt = "这一刻你什么感觉？"
reactions = [
  { id: "fire", emoji: "🔥", label: "爽" },
  { id: "sad", emoji: "😭", label: "心疼" },
  { id: "hooked", emoji: "😍", label: "上头" }
]
```

同一个时间点、同一句 prompt、同一组情绪素材，切换不同 UI presentation，便于直接比较交互方式本身。

## 6. 交互类型

第一版支持三个状态：

```text
none
poll_bar
emoji_hold
```

### 6.1 none

关闭互动 UI。

用途：

- 调试纯播放器；
- 对照不同互动 UI 对观看体验的影响；
- 准备最终展示时快速禁用实验控件。

### 6.2 poll_bar

底部投票条 baseline。

行为要求：

- 到达固定触发时间后出现；
- 展示固定 prompt 和 2 到 3 个选项；
- 用户点击一个选项后展示简单结果态；
- 结果态短暂停留后消失；
- 不记录事件，不更新统计。

实现上可以复用现有 `InteractionPollBar` 的视觉基础，但不要继续依赖后端 `InteractionPlan` 数据源。必要时可以新增一个 example 专用的轻量组件，避免把实验代码和正式业务模型强绑在一起。

### 6.3 emoji_hold

长按 emoji 蓄力互动。

行为要求：

- 到达固定触发时间后出现一个 emoji 按钮；
- 按钮应尽量不遮挡人物、字幕和进度条；
- 用户长按时展示蓄力反馈，例如放大、光圈扩散、进度环；
- 松手后触发短促视觉反馈，例如 emoji 粒子、光效或局部爆发；
- 反馈结束后自动收起；
- 不记录事件，不更新统计。

这个形态的目的不是收集投票结果，而是验证“低摩擦情绪表达”的手感。

## 7. 推荐代码结构

建议新增一个前端本地目录：

```text
apps/player-demo/src/interaction-examples/
  types.ts
  examples.ts
  InteractionLabControls.tsx
  InteractionExampleRenderer.tsx
  PollBarExample.tsx
  EmojiHoldExample.tsx
```

职责划分：

- `types.ts`：定义 example 相关类型；
- `examples.ts`：放固定实验数据；
- `InteractionLabControls.tsx`：开发用切换控件；
- `InteractionExampleRenderer.tsx`：根据当前 presentation type 渲染对应 UI；
- `PollBarExample.tsx`：底部投票条 example；
- `EmojiHoldExample.tsx`：长按 emoji example。

`PlayerScreen` 只负责传入当前播放时间、播放状态和当前选中的 example，不承载具体互动 UI 细节。

## 8. 建议类型

第一版可以使用轻量本地类型，不直接复用后端 `InteractionPlan`：

```ts
export type InteractionPresentationType = "none" | "poll_bar" | "emoji_hold";

export type InteractionReaction = {
  id: string;
  emoji: string;
  label: string;
};

export type InteractionExample = {
  id: string;
  label: string;
  presentationType: InteractionPresentationType;
  triggerTimeSec: number;
  prompt: string;
  reactions: InteractionReaction[];
};
```

原因：

- 当前目标是 UI 试验，不是策略系统；
- 非投票型互动不一定天然对应 `InteractionPlan` 的选项结构；
- 可以避免前端实验代码被后端契约过早限制；
- 后续确定最终方案后，再考虑和正式 `InteractionPlan` 对齐。

## 9. 播放器集成方式

`PlayerScreen` 建议增加三类状态：

```text
selectedPresentationType
hasTriggeredExample
exampleDismissed
```

基本规则：

1. 当 `currentTime >= triggerTimeSec` 且视频已开始播放时，允许展示当前 example；
2. 如果用户 seek 回触发时间之前，应重置 example 状态；
3. 切换 presentation type 时，应重置 example 状态；
4. 暂停视频时，已展示的 UI 可以保留，但动画类反馈应暂停或保持静止；
5. 不要阻断播放控制和进度条拖拽。

## 10. UI 位置建议

Interaction Lab 控制入口：

- 只在 `ENABLE_INTERACTION_LAB === true` 时展示；
- 可放在右上角或现有 debug 区域；
- 使用小型 segmented control 或按钮组；
- 不要占用主要观看区域。

互动 UI：

- `poll_bar` 放在底部安全区域上方，避免压住进度条；
- `emoji_hold` 可放在右侧中下区域或底部偏右区域；
- 避免遮挡字幕、人脸和关键剧情区域；
- 视觉反馈应短促，不应长时间覆盖视频。

## 11. 验收标准

1. 开发模式下可以看到 Interaction Lab 控制入口；
2. 可以切换 `Off`、`Poll Bar`、`Emoji Hold`；
3. `Off` 模式下固定触发点不会出现互动 UI；
4. `Poll Bar` 模式下，到达固定触发时间后出现底部投票条；
5. `Poll Bar` 点击选项后出现短暂结果态；
6. `Emoji Hold` 模式下，到达固定触发时间后出现 emoji 按钮；
7. `Emoji Hold` 长按时有持续视觉反馈；
8. `Emoji Hold` 松手后有短促结束反馈；
9. 切换模式或 seek 回触发点前，互动 UI 状态会重置；
10. 不调用后端 interaction plan 或 event 上报接口；
11. 不破坏视频播放、弹幕、进度条拖拽和后端视频加载；
12. `npm run typecheck` 通过；
13. 相关前端测试通过。

## 12. 建议实现顺序

1. 新增 `interaction-examples` 类型和固定 example 数据；
2. 新增 Interaction Lab 控制入口；
3. 新增 `InteractionExampleRenderer`；
4. 接入 `poll_bar` example；
5. 接入 `emoji_hold` example；
6. 在 `PlayerScreen` 中完成触发、重置和禁用逻辑；
7. 补充必要测试；
8. 手动检查播放、seek、暂停和切换模式。

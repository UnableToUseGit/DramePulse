# 数据层模块设计

## 1. 模块定位

数据层负责管理 DramePulse 的内容数据、结构化资产、用户事件和统计结果。

数据层不解释业务含义，不判断高光质量，也不生成互动策略。

## 2. 核心数据对象

### 2.1 Video Metadata

记录视频 ID、标题、剧名、集数、时长、播放地址和资源来源。

### 2.2 Subtitle Segment

记录字幕文本及其起止时间，是高光识别和剧情问答的重要文本上下文。

### 2.3 Highlight Asset

记录高光点的时间范围、类型、情绪、强度、摘要、原因、置信度和状态。

### 2.4 Interaction Plan

记录互动触发时间、互动类型、问题、选项、反馈规则、展示位置和状态。

### 2.5 User Event

记录用户在播放和互动过程中的行为，例如曝光、点击、反馈展示、关闭、暂停和 seek。

### 2.6 Stats

记录互动结果、选项分布、高光点表现和策略更新结果。

## 3. 数据契约

核心契约位于 `packages/contracts/`：

- `highlight-asset.schema.json`
- `interaction-plan.schema.json`
- `user-event.schema.json`

数据契约用于保证算法、后端和前端理解同一组字段，避免模块之间隐式耦合。

## 4. 存储形态

MVP 阶段支持本地 SQLite 和样例 JSON 数据。云端部署可以扩展到 MySQL、OSS 和 CDN。

## 5. 当前实现草稿

当前仓库已经包含样例数据、SQLite 数据库、JSON Schema、示例契约和数据处理脚本。

后续需要补充实体关系图、表结构说明、样例数据路径和迁移策略。

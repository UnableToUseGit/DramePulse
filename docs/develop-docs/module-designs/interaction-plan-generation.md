# 交互方案生成模块设计

> 本文档记录早期互动方案生成设计。当前算法验证阶段不再维护旧 `interaction_plan_generation` pipeline，该实现已废弃并移除。

## 1. 模块定位

交互方案生成模块负责把高光点识别结果转化为前端可以直接渲染的互动方案。

在系统链路中，它位于高光点识别模块之后、播放器互动渲染模块之前：

```text
Highlight Asset
  ↓
交互方案生成模块
  ↓
Interaction Plan
  ↓
播放器内弹幕投票互动
```

本模块不负责识别高光点，也不负责前端 UI 渲染。它的核心职责是理解某个高光点附近的剧情语境，并生成适合移动端短剧观看场景的低摩擦互动方案。

MVP 阶段只支持一种互动类型：

```text
danmaku_poll
```

也就是弹幕投票。

## 2. 设计目标

第一版实现优先满足以下目标：

1. 根据 `Highlight Asset` 生成结构化 `Interaction Plan`；
2. 结合高光点附近的视频帧、字幕和历史弹幕，生成贴合剧情语境的投票问题与选项；
3. 输出结果符合 `packages/contracts/schemas/interaction-plan.schema.json`；
4. 生成过程可解释、可回退，适合比赛答辩展示；
5. 不依赖复杂用户画像、推荐系统或在线学习能力。

## 3. 输入

### 3.1 必需输入

#### Highlight Asset

`Highlight Asset` 是本模块的主输入，用于确定互动的剧情锚点。

关键字段包括：

- `highlight_id`：高光点 ID；
- `video_id`：视频 ID；
- `start_time`：高光开始时间；
- `end_time`：高光结束时间；
- `highlight_type`：高光类型；
- `emotion`：主要激发情绪；
- `intensity`：情绪强度；
- `summary`：高光剧情摘要；
- `reason`：适合触发互动的原因；
- `confidence`：识别置信度。

#### video_file_path

视频文件路径。

模块根据 `Highlight Asset.start_time` 和 `Highlight Asset.end_time` 从视频中抽取高光点附近的关键帧，帮助大模型理解人物表情、画面关系、动作和场景氛围。

当前实现会抽取少量关键帧，并将时间戳以文本形式插入多图请求中。

#### subtitle_file_path

字幕文件路径。

模块根据高光时间窗口抽取相关字幕，作为大模型理解剧情语义的主要文本上下文。

建议抽取范围：

```text
[highlight.start_time - 8s, highlight.end_time + 5s]
```

### 3.2 当前实现的额外输入

#### danmaku_items

当前实现直接从 `video_id` 对应的数据文件加载弹幕数组，并作为显式输入传入 pipeline。

每条弹幕的典型结构参考：

```json
{
  "time_sec": 39.5,
  "text": "这个反转绝了",
  "digg_count": 88,
  "score": 99.0
}
```

模块会将这些弹幕整理成适合 prompt 阅读的文本上下文。

### 3.3 可选输入

#### historical_stats

历史用户行为统计在概念上仍可作为可选输入，但当前实现未接入。

后续可以用于：

- 根据历史点击率调整选项排序；
- 根据关闭率决定是否触发互动；
- 根据高光点表现调整问题风格；
- 根据选项点击分布优化文案。

#### strategy_config

策略配置在概念上仍可保留，但当前实现主要通过 pipeline 参数和 fallback 模板控制。

## 4. 输出

模块输出 `Interaction Plan`。

该对象必须符合：

```text
packages/contracts/schemas/interaction-plan.schema.json
```

MVP 输出示例：

```json
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
    },
    {
      "option_id": "o_002",
      "text": "爽到了",
      "danmaku_text": "这波爽到了！",
      "rank": 2,
      "base_score": 0.7
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
```

## 5. 处理流程

### 5.1 上下文抽取

模块首先根据 `Highlight Asset` 抽取生成所需上下文。

流程：

```text
Highlight Asset
  ↓
读取 video_file_path
  ↓
抽取高光附近关键帧
  ↓
读取 subtitle_file_path
  ↓
抽取高光附近字幕
  ↓
读取或接收当前视频弹幕
  ↓
组织大模型输入上下文
```

抽取结果可以组织为：

```json
{
  "highlight": {},
  "subtitle_context": [],
  "frame_context": [],
  "danmaku_context": []
}
```

### 5.2 大模型生成草稿

模块将以下信息提供给大模型：

- `Highlight Asset`；
- 高光点附近字幕；
- 高光点附近视频帧；
- 该视频弹幕上下文；
- 生成约束。

大模型负责生成 `Interaction Plan` 的内容型字段：

- `question`；
- `options[].text`；
- `options[].danmaku_text`；
- `options[].base_score`；
- `feedback` 文案建议。

MVP 阶段，大模型不负责决定以下字段：

- `interaction_id`；
- `highlight_id`；
- `video_id`；
- `trigger_time`；
- `expire_time`；
- `interaction_type`；
- `status`。

这些字段由系统根据输入和策略配置补全。

### 5.3 规则补全与校验

大模型输出不能直接下发给前端，必须经过规则校验与补全。

校验规则包括：

1. `interaction_type` 必须为 `danmaku_poll`；
2. `options` 数量必须为 2 到 3 个；
3. 每个选项必须包含 `text` 和 `danmaku_text`；
4. 选项文案要短，适合移动端点击；
5. `danmaku_text` 要像真实弹幕表达；
6. 不允许输出与剧情无关的选项；
7. 不允许输出攻击性、低俗或明显不适合展示的文案；
8. 输出必须符合 JSON Schema；
9. 缺失的 ID、时间、状态字段由系统补全。

### 5.4 fallback

如果大模型生成失败或校验不通过，模块使用内置 fallback 模板生成基础弹幕投票。

示例规则：

```text
highlight_type = 身份揭露
  → question: 这波反转你怎么看？
  → options: [卧槽反转了, 爽到了]

highlight_type = 打脸反杀
  → question: 这一幕爽不爽？
  → options: [太争气了, 爽到了]

highlight_type = 甜蜜撒糖
  → question: 这段什么感觉？
  → options: [磕到了, 有点甜]

highlight_type = 冲突爆发
  → question: 你站哪边？
  → options: [站女主, 站男主]
```

fallback 的目标不是生成最优文案，而是保证端到端链路可运行、可演示。

## 6. 当前接口形态

当前代码实现采用纯业务 pipeline：

```python
generate_interaction_plan(
    highlight_asset,
    video_file_path,
    subtitle_file_path,
    danmaku_items,
    strategy_config=None,
    historical_stats=None,
)
```

其中 `danmaku_items` 直接使用当前视频的弹幕数据，数据结构参考 `data/case1/ep01.json` 中的 `danmaku` 数组。

这种设计让数据读取职责留在上游数据准备流程中，交互方案生成模块只负责消费已经准备好的视频、字幕、高光和弹幕上下文。

## 7. 模块边界

### 7.1 本模块负责

1. 根据高光点组织生成上下文；
2. 抽取高光附近字幕；
3. 抽取高光附近视频帧；
4. 消费当前视频弹幕上下文；
5. 调用大模型生成弹幕投票草稿；
6. 校验并补全 `Interaction Plan`；
7. 在生成失败时使用 fallback 模板。

### 7.2 本模块不负责

1. 不识别高光点；
2. 不长期存储用户事件；
3. 不计算点击率、关闭率和回看率；
4. 不执行策略更新；
5. 不渲染前端 UI；
6. 不控制播放器；
7. 不实现用户画像或推荐逻辑。

## 8. 与其他模块的关系

### 8.1 与高光点识别模块

高光点识别模块输出 `Highlight Asset`。

交互方案生成模块消费 `Highlight Asset`，但不修改它。

### 8.2 与播放器前端

播放器前端只消费生成后的 `Interaction Plan`。

前端不需要知道该方案来自固定模板还是大模型生成。

### 8.3 与统计策略更新模块

MVP 阶段，统计策略更新模块不参与交互方案生成。

后续可以将统计结果作为可选输入，用于调整：

- 是否触发互动；
- 选项排序；
- 选项分数；
- 反馈展示方式。

## 9. MVP 实现边界

第一版只实现：

1. 单个 `Highlight Asset` 到单个 `Interaction Plan` 的生成；
2. `danmaku_poll` 一种互动类型；
3. 字幕窗口抽取；
4. 少量关键帧抽取；
5. 当前视频弹幕上下文；
6. 大模型生成问题和选项；
7. schema 校验；
8. fallback 模板。

第一版暂不实现：

1. 多互动类型自动选择；
2. 个性化互动方案；
3. 基于历史统计的排序更新；
4. A/B 测试；
5. 在线学习；
6. 复杂敏感内容审核系统。

## 10. 与实现保持一致的说明

当前实现已经固定了以下行为：

- 交互类型固定为 `danmaku_poll`；
- 大模型通过多模态 prompt 接收高光截图、字幕和弹幕上下文；
- `ARK_BASE_URL`、`ARK_API_KEY`、`ARK_MODEL` 通过脚本读取 `.env` 后注入；
- 生成失败时使用内置 fallback；
- 交互输出写入 `output/<video_id>/interaction_plan_generation.json`。

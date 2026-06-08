# 弹幕表达探查与心里话候选设计

## 1. 背景

`inner_voice_danmaku` 的目标是服务前端“心里话弹幕”功能：在合适的剧情时刻弹出一枚弹幕胶囊，用户向上轻推即可发送。

当前已有 pipeline 可以从弹幕中生成 `InnerVoiceDanmakuCue`，但在继续优化前，需要先回答三个问题：

1. 用户发送弹幕到底想表达什么内容；
2. 哪些内容获得了大量共鸣；
3. 哪些内容适合作为心里话弹幕被系统主动弹出。

新增的数据探查流程不直接替代现有生成 pipeline，而是作为算法迭代前的分析与人工校准工具。

## 2. 输入

第一版输入为真实弹幕 CSV：

```text
data/圈选剧前5集弹幕.csv
```

该文件使用 GB18030/GBK 类编码读取。原始字段映射为：

| 原始字段 | 归一化字段 | 说明 |
| --- | --- | --- |
| `剧名称` | `series_title` | 短剧名称 |
| `group_title` | `episode_title` | 集数标题，例如第 1 集 |
| `发弹幕时刻相对于视频起始时间偏移量` | `time_ms` | 弹幕相对视频起始时间，单位毫秒 |
| `累计点赞数` | `digg_count` | 弹幕累计点赞数 |
| `弹幕内容` | `text` | 弹幕正文 |

归一化后额外派生：

| 字段 | 说明 |
| --- | --- |
| `video_id` | 根据剧名和集数生成的稳定 ID |
| `time_sec` | `time_ms / 1000.0` |
| `comment_id` | 基于行号或字段生成的可追溯 ID |
| `clean_text` | 清洗后的弹幕文本 |

## 3. 输出

输出目录：

```text
output/danmaku_exploration/
```

第一版输出三类 JSON 产物。

### 3.1 `episode_profile.json`

用于回答“数据整体长什么样”。

每集记录：

- `video_id`
- `series_title`
- `episode_title`
- `danmaku_count`
- `clean_danmaku_count`
- `time_range_sec`
- `digg_distribution`
- `low_quality_text_count`
- `top_repeated_texts`
- `top_liked_texts`

### 3.2 `resonance_windows.json`

用于回答“哪些时间点有群体共鸣”。

每个窗口记录：

- `window_id`
- `video_id`
- `start_time`
- `end_time`
- `danmaku_count`
- `unique_text_count`
- `repeat_text_count`
- `digg_sum`
- `high_digg_count`
- `burst_score`
- `resonance_score`
- `top_comments`

### 3.3 `inner_voice_review_candidates.json`

用于人工复核“哪些内容适合作为心里话弹幕”。

每条候选记录：

- `candidate_id`
- `video_id`
- `window_id`
- `trigger_time`
- `duration_sec`
- `text`
- `intent_type`
- `source_comment_ids`
- `resonance_score`
- `inner_voice_fit_score`
- `recommendation`
- `reason`
- `review_status`

`review_status` 初始值为 `unreviewed`。人工复核时可以改为：

- `accepted`
- `rejected`
- `needs_rewrite`

## 4. 处理流程

整体流程：

```text
CSV
  -> 编码读取与字段归一化
  -> 文本清洗
  -> 每集基础画像
  -> 滑动窗口共鸣检测
  -> 高共鸣窗口 top 弹幕抽取
  -> 表达意图粗分类
  -> 心里话适配评分
  -> 人工 review 候选输出
```

### 4.1 文本清洗

清洗规则保持保守，只做不会改变语义的处理：

1. 去除首尾空白和连续空白；
2. 过滤空文本；
3. 过滤纯标点、纯数字、纯表情占位；
4. 标记但不立即删除泛低语义文本，例如 `哈哈哈`、`笑死了`、`啊啊啊`；
5. 保留原文和清洗文本，方便回溯。

泛低语义文本可能有共鸣价值，但通常不直接适合作为心里话胶囊，所以只降级，不在早期完全丢弃。

### 4.2 共鸣窗口检测

按每集独立做滑动窗口聚合。

默认参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `window_sec` | `8.0` | 共鸣窗口长度 |
| `step_sec` | `2.0` | 滑动步长 |
| `min_window_danmaku_count` | `4` | 最小弹幕数 |
| `max_windows_per_episode` | `50` | 每集最多保留高共鸣窗口数 |

窗口分数拆成两类：

```text
resonance_score = 群体共鸣强度
inner_voice_fit_score = 心里话胶囊适配度
```

这样可以避免把“共鸣很强但不适合弹出”的内容误选为前端候选。

窗口召回只在基础分数之外增加两条硬规则：

1. 命中 `ACTOR_CHARM_KEYWORDS` 的高分共鸣窗口优先保留；
2. `EMOTION_BURST_KEYWORDS` 密集出现的窗口排除，避免把 `哈哈哈`、`爽`、`啊啊啊`、表情占位等简单情绪表达召回为心里话弹幕。

`plot_reaction`、`meme`、`stance` 暂不作为召回关键词，避免过早把边界不清的表达类型固化进规则。

### 4.3 表达意图粗分类

第一版使用规则做粗分类，不要求一次性精确分类全量弹幕。

分类范围：

| intent type | 含义 | 示例 |
| --- | --- | --- |
| `actor_charm` | 角色或演员魅力表达 | 他这个眼神绝了 |
| `emotion_burst` | 底层情绪宣泄 | 笑死我了 |
| `low_signal` | 缺少可用语义 | 哈哈哈 |
| `unsafe` | 攻击、低俗或不适合前端弹出 | 需要过滤的内容 |

第一版优先保留 `actor_charm`。`emotion_burst` 用于排除简单情绪密集区间，不作为心里话弹幕主候选。剧情评价、玩梗和观点表达后续交给人工 review 和 LLM 识别，不先用关键词硬召回。

### 4.4 心里话适配评分

适合作为心里话弹幕的文本应满足：

1. 6 到 18 个中文字符优先；
2. 像真实用户会发送的弹幕；
3. 有具体剧情、角色或氛围指向；
4. 不只是单纯情绪词；
5. 不像剧情总结或运营文案；
6. 不泄露后续剧情；
7. 不攻击演员、角色或其他用户；
8. 不需要复杂上下文也能在当前窗口成立。

推荐结果分为：

| recommendation | 含义 |
| --- | --- |
| `recommended` | 可进入人工 review 的优先候选 |
| `borderline` | 有价值但需要人工判断或改写 |
| `not_recommended` | 不适合作为心里话胶囊 |

## 5. 模块边界

建议新增分析脚本或 pipeline，但不直接修改现有 `InnerVoiceDanmakuPipeline`。

边界如下：

- 探查流程负责读取 CSV、统计、聚合、输出 review 候选；
- `inner_voice_danmaku` 负责从已确认的方法中生成前端 cue；
- 前端只消费最终 cue，不消费探索阶段 debug 产物；
- 人工 review 结果后续可以作为调参、过滤规则和评估集的依据。

## 6. 错误处理

第一版需要显式处理：

1. CSV 编码读取失败：报告文件路径和尝试过的编码；
2. 缺少必要字段：报告缺失字段并停止；
3. 时间或点赞字段无法解析：跳过该行并计入 diagnostics；
4. 单集弹幕过少：输出 profile，但不生成 resonance window；
5. 输出目录不存在：自动创建；
6. 写出失败：报告目标路径和异常信息。

## 7. 验证方式

单元测试覆盖：

1. GB18030 CSV 可以正确读取；
2. 字段可以归一化为 `series_title`、`episode_title`、`time_sec`、`digg_count`、`text`；
3. 低质文本会被标记；
4. 滑动窗口可以找到弹幕密集区；
5. 高赞和重复文本会提高 `resonance_score`；
6. 泛情绪词不会直接得到高 `inner_voice_fit_score`；
7. 输出 JSON 包含人工 review 所需字段。

人工验收标准：

1. 每集能看到清晰的数据画像；
2. 高共鸣窗口附近确实有明显弹幕聚集；
3. 候选文案能追溯到真实弹幕；
4. 候选文案读起来像用户愿意一推发送的话；
5. 被过滤内容有可解释原因。

## 8. 非目标

第一版不做：

1. 不直接生成最终前端 `inner_voice_cues.json`；
2. 不修改共享 contract schema；
3. 不接入用户发送事件闭环；
4. 不做全量复杂语义聚类；
5. 不做模型训练；
6. 不要求 LLM 处理完整 CSV；
7. 不把所有高共鸣内容都视为适合弹出。

## 9. 后续扩展

当人工 review 积累后，可以继续推进：

1. 将 `accepted` 候选转成 `inner_voice_danmaku` 的评估集；
2. 用 review 结果调整 intent 分类和适配评分；
3. 将字幕上下文加入候选解释；
4. 对 accepted 候选生成最终 `InnerVoiceDanmakuCue`；
5. 在前端播放器中验证真实触发时机和胶囊发送体验；
6. 用用户轻推发送率反哺 `inner_voice_fit_score`。

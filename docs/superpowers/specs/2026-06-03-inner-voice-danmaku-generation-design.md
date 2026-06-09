# 心里话弹幕生成算法设计

## 1. 背景

前端已经定义了“心里话弹幕”交互：系统在剧情附近给出一句待发送弹幕草稿，用户觉得准确，就轻推发送；没感觉则不操作，草稿自然消失。

这个交互承载的不是 `爽点`、`笑点`、`甜点`、`泪点` 这类底层情绪按钮，而是更高语义的观众表达。第一版先收窄到剧情反应、玩梗和角色魅力，避免表达类型过散导致召回与评估都难以稳定。

算法侧第一版目标是利用真实弹幕资源，从海量弹幕中找到观众共鸣表达集中的位置，并抽取或轻量改写出一句前端可直接展示的心里话弹幕。

## 2. 模块定位

建议新增独立模块：

```text
inner_voice_danmaku_generation
```

模块职责：

1. 读取单集真实弹幕；
2. 发现弹幕共鸣峰；
3. 识别高语义表达类型；
4. 选择或改写一句可发送文案；
5. 输出前端 `InnerVoiceDanmakuCue` 列表；
6. 输出 debug 信息，方便人工检查生成依据。

第一版不和高光识别结果对齐：

- 不读取 `highlight_recognition.json`；
- 不消费 `resonance_cues`；
- 不判断候选点是否属于剧情高光；
- 不给现有 `Highlight Asset` 回填字段；
- 输出中的 `highlightId` 使用空字符串或派生的 inner voice ID 占位，前端不依赖它做匹配。

这样做的原因是心里话弹幕的核心依据是真实观众表达，而不是算法判断出的剧情刺激点。先保持模块独立，可以更清楚地评估“弹幕共鸣挖掘”本身是否成立。

## 3. 输入

第一版输入只需要真实弹幕数据。优先复用已有 CSV 读取能力：

- `scripts/algorithm_danmaku_csv.py`
- `scripts/analyze_danmaku_expression_triggers.py`

单条弹幕归一化结构：

```json
{
  "danmaku_id": "csv_beiwang_ep01_102",
  "series_id": "beiwang",
  "episode_id": "ep01",
  "time_sec": 38.2,
  "text": "她终于怼回去了",
  "digg_count": 12
}
```

必要字段：

| 字段 | 说明 |
| --- | --- |
| `time_sec` | 弹幕出现时间，单位秒 |
| `text` | 弹幕正文 |
| `digg_count` | 点赞数，没有则按 0 处理 |
| `danmaku_id` | debug 溯源使用，可选但建议保留 |

## 4. 输出

第一版直接输出前端可消费的 camelCase JSON。

输出路径建议：

```text
output/inner_voice_danmaku/<video_id>/inner_voice_cues.json
```

示例：

```json
{
  "videoId": "beiwang_ep01",
  "seriesId": "beiwang",
  "episodeId": "ep01",
  "createdAt": "2026-06-03T12:00:00Z",
  "cues": [
    {
      "cueId": "iv_beiwang_ep01_001",
      "videoId": "beiwang_ep01",
      "highlightId": "iv_beiwang_ep01_001",
      "triggerTime": 38.0,
      "durationSec": 5.0,
      "text": "她终于怼回去了",
      "danmakuTrack": 1
    }
  ],
  "debug": {
    "sourceDanmakuCount": 352,
    "candidateWindowCount": 18,
    "selectedCueCount": 1
  }
}
```

同时输出 debug 文件：

```text
output/inner_voice_danmaku/<video_id>/inner_voice_debug.json
```

debug 中保留：

- 候选窗口起止时间；
- 窗口分数；
- 弹幕数量和去重数量；
- top comments；
- 被选中的 source comment；
- LLM 改写前后的文本；
- 过滤原因；
- 最终排序依据。

## 5. 表达类型

心里话弹幕不沿用情绪按钮分类。第一版只使用以下 intent type，仅用于算法筛选和 debug，不要求前端展示：

| intent type | 含义 | 示例 |
| --- | --- | --- |
| `plot_reaction` | 对剧情动作或台词的即时反应 | 她终于怼回去了 |
| `meme` | 玩梗、网络语、氛围梗 | 这谁顶得住 |
| `actor_charm` | 演员或角色魅力 | 他看她的眼神不对劲 |

暂不进入第一版的类型：

- CP、暧昧和关系解读；
- 剧情预判和反转预感；
- 站队、替角色说话；
- 吐槽、反讽。

这些类型仍然有产品价值，但语义边界更容易和剧情高光、情绪按钮或评论表达混在一起。后续等前三类跑通后，再按数据表现逐类扩展。

过滤纯底层情绪表达：

- `哈哈哈哈`
- `爽`
- `笑死`
- `哭了`
- `甜`

这些内容更适合情绪按钮，不适合作为“只给一句”的心里话草稿，除非它们和具体剧情、角色或观点绑定。

## 6. 算法流程

整体流程：

```text
真实弹幕
-> 清洗与归一化
-> 时间窗口共鸣峰检测
-> 语义表达簇识别
-> 候选文案筛选
-> LLM 窗口内识别 plot_reaction / meme
-> 去重、限量、排序
-> 输出 inner_voice_cues.json 和 debug
```

### 6.1 清洗与归一化

基础清洗规则：

1. 去掉空文本；
2. 去掉纯标点、纯表情、纯数字；
3. 去掉明显过长文本，默认超过 24 个中文字符先过滤；
4. 合并完全相同文本，保留出现次数、最高点赞和时间分布；
5. 标记疑似低质内容，例如辱骂、低俗、无意义刷屏；
6. 保留短文本优先，但不强制所有候选都在 18 字以内，LLM 精修阶段可以压缩。

### 6.2 共鸣窗口检测

用滑动窗口发现弹幕集中表达的位置。

默认参数建议：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `window_sec` | 8.0 | 共鸣检测窗口长度 |
| `step_sec` | 2.0 | 滑动步长 |
| `min_window_danmaku_count` | 4 | 最小弹幕数 |
| `min_unique_text_count` | 2 | 最小去重文本数 |
| `max_cues_per_episode` | 8 | 单集最多输出 cue |

窗口分数：

```text
window_score =
  danmaku_count_weight
+ unique_text_weight
+ like_weight
+ burst_weight
+ semantic_cohesion_weight
- low_quality_penalty
```

各项含义：

- `danmaku_count_weight`：窗口内弹幕越多，说明表达欲越强；
- `unique_text_weight`：去重后仍有多条表达，说明不是单条刷屏；
- `like_weight`：高点赞弹幕增加可信度；
- `burst_weight`：相对前后窗口突增，说明此处可能是共鸣峰；
- `semantic_cohesion_weight`：多条弹幕表达同一类含义；
- `low_quality_penalty`：刷屏、纯情绪词、攻击性内容降权。

### 6.3 语义表达簇识别

第一版采用混合策略：

```text
actor_charm：规则优先
plot_reaction：候选窗口内 LLM 识别
meme：候选窗口内 LLM 识别
```

`actor_charm` 的语言信号直接，适合规则识别。关键词可以包括：

- 帅、美、漂亮、好看、颜值、气质；
- 眼神、表情、演技、哭戏；
- 老公、老婆、姐姐、妹妹、小奶狗；
- 绝了、鲨我、顶不住。

规则命中后仍要做质量过滤，避免把纯泛化夸赞当成高质量心里话。例如 `好帅` 可以作为弱信号，但不一定适合直接输出；`他看她的眼神不对劲` 更适合作为代表句。

`plot_reaction` 和 `meme` 不用规则硬判。它们依赖剧情语境和观众表达方式，同一句话在不同场景里可能含义不同。第一版只把共鸣窗口、top comments 和可选字幕上下文交给 LLM，让 LLM 判断窗口内是否形成了这两类语义簇。

LLM 在这一阶段的职责：

1. 判断窗口内是否存在 `plot_reaction` 或 `meme`；
2. 判断多条弹幕是否在表达同一个心里话；
3. 给出代表句，优先从真实弹幕中选择，其次轻量压缩；
4. 返回 source comment ids，保证结果可溯源；
5. 给出置信度和一句简短原因，供 debug 使用。

LLM 不负责：

- 扫全量弹幕；
- 判断窗口是否值得处理；
- 凭空生成没有弹幕依据的新观点；
- 生成多个给用户选择的文案。

单个候选窗口的 LLM 输入控制在 top 20 到 40 条弹幕内，按点赞、文本质量和时间接近度排序。这样成本可控，也方便在 debug 文件中复盘。

LLM 输出示例：

```json
{
  "clusters": [
    {
      "intentType": "plot_reaction",
      "representativeText": "她终于怼回去了",
      "sourceCommentIds": ["dm_12", "dm_18", "dm_22"],
      "confidence": 0.86,
      "reason": "多条弹幕都在表达观众对女主反击的即时反应。"
    }
  ]
}
```

如果 LLM 返回空簇或置信度不足，该窗口只保留规则识别出的 `actor_charm` 候选，不强行生成 `plot_reaction` 或 `meme`。

一个窗口可以有多个 intent，但最终 cue 需要经过后处理控制密度。同一窗口内优先保留分数最高、文案最适合发送的一条。

### 6.4 候选文案筛选

候选文案优先从真实弹幕中抽取，不凭空生成。

候选来源分两类：

1. `actor_charm` 规则簇的代表句；
2. LLM 返回的 `plot_reaction` / `meme` 代表句。

所有候选都必须通过统一质量校验：

单条候选文案分数：

```text
text_score =
  source_frequency
+ digg_score
+ window_score
+ length_score
+ specificity_score
+ colloquial_score
- generic_emotion_penalty
- toxicity_penalty
- spoiler_penalty
```

偏好的文案：

- 6 到 14 个中文字符优先；
- 最多不超过 18 个中文字符；
- 像真实观众会发的弹幕；
- 和当前剧情或角色有关；
- 有观点、有梗或有具体指向；
- 不像剧情总结；
- 不像运营文案；
- 不泄露后续剧情。

### 6.5 LLM 精修

LLM 在第一版不是纯“精修”工具，而是 `plot_reaction` 和 `meme` 的窗口内语义簇识别工具。

输入给 LLM：

- 当前候选窗口时间；
- 窗口内 top comments，带 comment id、时间、点赞和清洗后文本；
- 只允许判断 `plot_reaction` 和 `meme`；
- 可选的附近字幕文本；
- 文案长度和风格约束。

LLM 输出要求：

```json
{
  "clusters": [
    {
      "intentType": "plot_reaction",
      "representativeText": "她终于怼回去了",
      "sourceCommentIds": ["dm_12", "dm_18"],
      "confidence": 0.86,
      "reason": "多条弹幕都在表达女主反击带来的即时反应。"
    }
  ]
}
```

LLM 约束：

1. 每个 cluster 只能输出一句代表文案；
2. 单个窗口最多输出 2 个 cluster；
3. 不做剧情总结；
4. 不使用官方口吻；
5. 不编造真实弹幕中没有依据的含义；
6. 优先选择真实弹幕原句，其次压缩、修饰真实弹幕；
7. `sourceCommentIds` 必须来自输入 comment ids。

如果 LLM 失败或返回不合格文案，不为 `plot_reaction` 和 `meme` 生成结果；该窗口仍可输出规则识别出的 `actor_charm` 候选。

### 6.6 去重、限量、排序

后处理规则：

1. 文案完全相同的 cue 去重；
2. 语义高度相似且时间接近的 cue 合并；
3. 相邻 cue 间隔默认不小于 12 秒；
4. 单集默认最多输出 8 条；
5. 按综合分排序后，再按时间顺序输出给前端；
6. `durationSec` 默认 5 秒，可通过 CLI 调整；
7. `danmakuTrack` 使用确定性分配，例如 `index % 3`。

## 7. CLI 设计

建议新增脚本：

```text
scripts/run_inner_voice_danmaku_generation.py
```

单集运行：

```bash
python scripts/run_inner_voice_danmaku_generation.py \
  --data-root data \
  --series-id beiwang \
  --episode-id ep01 \
  --output-root output/inner_voice_danmaku
```

批量运行可以后续再加，或第一版直接让脚本在未指定 `series-id`、`episode-id` 时遍历 CSV 中所有剧集。

重要参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--window-sec` | `8.0` | 共鸣窗口长度 |
| `--step-sec` | `2.0` | 滑动步长 |
| `--max-cues-per-episode` | `8` | 每集最多 cue 数 |
| `--duration-sec` | `5.0` | 前端展示时长 |
| `--enable-llm-refine` | 关闭 | 是否启用 LLM 精修 |
| `--min-window-score` | `6.0` | 最小窗口分数，后续可通过实验调整 |
| `--debug` | 开启 | 是否输出 debug 文件 |

## 8. 测试与验收

单元测试重点：

1. CSV 弹幕归一化可以被复用；
2. 低质文本会被过滤；
3. 窗口检测能找到弹幕密集区；
4. 重复文本会合并计数；
5. 候选文案优先选择短、具体、高赞文本；
6. LLM 失败时能回退到规则结果；
7. 输出 JSON 字段满足前端 `InnerVoiceDanmakuCue`；
8. 单集 cue 数、间隔、去重规则生效。

人工验收：

1. 每集输出 3 到 8 条优先，不强行填满；
2. 文案读起来像真实弹幕；
3. 文案不是单纯情绪词；
4. cue 时间附近能在真实弹幕中看到相似表达；
5. debug 信息能解释为什么选这句；
6. 前端可以直接加载 `inner_voice_cues.json` 做 demo。

## 9. 非目标

第一版不做：

- 不和现有高光识别结果对齐；
- 不要求每个高光点都有心里话；
- 不修改共享 `Interaction Plan` schema；
- 不生成多句供用户选择；
- 不做用户个性化；
- 不使用视频帧做多模态验证；
- 不把普通弹幕全量重排；
- 不将心里话发送事件接入后端闭环。

## 10. 后续扩展

第一版验证有效后，可以继续做：

1. 接入字幕上下文，提高 LLM 精修的剧情贴合度；
2. 和高光识别结果做弱对齐，发现算法漏召回位置；
3. 将 `inner_voice_danmaku` 纳入统一互动方案下发；
4. 用用户轻推发送率评估文案质量；
5. 根据剧种和角色关系调整 intent 词表；
6. 扩展 CP 解读、剧情预判、站队和吐槽等 intent；
7. 在算法 review 工具中展示心里话候选和 source danmaku。

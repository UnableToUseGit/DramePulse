# Dual Branch Expression Trigger 设计记录

## 1. 背景

当前 `pipelines/expression_trigger/workflow.py` 的效果暴露出一个核心问题：它把任务建模成“直接从视频和字幕中识别四类表达触发点”。这会让剧情结构判断、用户表达判断和触发时间精修混在同一个模型决策里。

在 `jialijiawai` 两集验证中，问题集中表现为：

- 剧情层面的释放点能部分命中，例如 `jialijiawai_ep01` 中男主取消反派评优资格的爽点；
- 非剧情结构型表达容易漏召回，例如 `jialijiawai_ep01` 中“毒素进脑壳 / 我帮你消毒”的 punchline；
- 同一剧情段落中模型容易按剧情结构而不是用户表达分类，例如 `jialijiawai_ep02` 中求婚和答应结婚片段被误判为笑点或爽点；
- 只调 prompt 难以修复，因为当前链路缺少“剧情高光候选”和“表达触发决策”的边界。

因此新方案改为 dual branch：

```text
视频 + 字幕 + 章节上下文
  ├─ Plot Beat Branch：识别剧情结构高光候选
  └─ Punchline Branch：识别非剧情结构型笑点候选
        ↓
候选合并
        ↓
Triggerability Judge：可触发判断、表达分类、排序、Top-K、时间精修
        ↓
expression_triggers.json
```

## 2. 设计目标

第一版只解决“播放器真正要弹出的 expression triggers”，不是完整高光资产体系。

目标：

1. 将剧情高光识别和 expression trigger 决策拆开；
2. 支持剧情结构候选和 punchline 候选两类来源；
3. 最终 expression trigger 只输出四类：`爽点`、`甜点`、`泪点`、`笑点`；
4. 每集默认最多输出 `top_k=4` 个 trigger；
5. 候选和最终 trigger 使用统一时间字段：`start_time`、`end_time`、`trigger_time`；
6. 最终资产保持干净，debug 资产保留候选、拒绝原因、排序过程。

非目标：

1. 第一版不支持 `震惊` 作为最终表达类型；
2. 第一版不做角色魅力、BGM 梗、观众站队、剧终评价；
3. 第一版不引入训练模型或复杂监督学习；
4. 第一版不改变前端互动形态，只提供更准确的触发资产。

## 3. 核心定义

### 3.1 Candidate

Candidate 是一个语义片段，不是单个点。

所有候选都使用以下时间字段：

- `start_time`：理解该候选所需的上下文开始；
- `end_time`：该候选语义片段结束；
- `trigger_time`：如果该候选最终成为 trigger，最适合播放器触发表达的时间点。

候选阶段的 `trigger_time` 是模型初判，后续可由 Triggerability Judge 精修。

### 3.2 Expression Trigger

Expression Trigger 是最终给播放器消费的表达触发资产。

它同样使用：

- `start_time`
- `end_time`
- `trigger_time`

不再引入 `release_time`、`cue_time`、`ui_trigger_time`。如果前端需要略晚弹出，可以在播放层基于 `trigger_time` 做固定延迟，不写入算法资产。

### 3.3 Triggerability

Triggerability 不是简单布尔过滤器，而是最终决策器。它负责：

1. 判断候选语义是否可以作为 expression trigger；
2. 对所有可触发候选统一排序；
3. 根据 `top_k` 仅保留最高质量的 trigger；
4. 精修 `start_time`、`end_time`、`trigger_time`。

## 4. Branch A：Plot Beat Branch

Plot Beat Branch 先识别剧情结构上的关键事件，不直接决定最终 trigger。

第一版候选类型收敛为：

- `conflict_start`：冲突开始；
- `conflict_escalation`：冲突升级；
- `face_slap`：打脸；
- `payback`：反击、报复、夺回主动权；
- `reversal`：反转；
- `rescue_success`：救人、解围、承诺兑现；
- `relationship_advance`：关系升温、确认、亲密推进；
- `family_emotional_payoff`：亲情、守护、承诺、理解等情感兑现。

这些候选不等于 trigger。例如：

- `conflict_start` 通常只是 setup，不适合直接触发；
- `conflict_escalation` 如果只是加压，也通常不触发；
- `face_slap`、`payback` 常转为 `爽点`；
- `relationship_advance` 常转为 `甜点`；
- `family_emotional_payoff` 常转为 `泪点`；
- `reversal` 需要由 Triggerability 判断它到底是爽、甜、泪、笑，还是不触发。

Plot candidate 的建议输出字段：

```json
{
  "candidate_id": "plot_jialijiawai_ep02_001",
  "source_branch": "plot_beat",
  "candidate_type": "payback",
  "start_time": 58.0,
  "end_time": 72.0,
  "trigger_time": 67.0,
  "summary": "女主看到儿子被嫂子刁难后直接掀桌。",
  "setup": "嫂子在餐桌上刁难女主的儿子。",
  "turning_point": "女主到场后直接掀桌反击。",
  "payoff": "被欺负的一方夺回主动权，形成解气释放。",
  "evidence": [
    "64.790-67.190 你在我家吃饭，走就走了！"
  ]
}
```

## 5. Branch B：Punchline Branch

Punchline Branch 只捕捉非剧情结构型笑点。

第一版只服务 `笑点`，不处理角色魅力、震惊、站队或剧终评价。

它负责识别：

- 一句包袱台词；
- 方言梗；
- 夸张说法；
- 反差回应；
- 尴尬误会落点；
- 台词和动作共同形成的笑点。

Punchline 候选也必须是范围加 `trigger_time`。范围通常比 plot candidate 更短，但仍要包含理解笑点所需的铺垫。

示例：

```json
{
  "candidate_id": "punchline_jialijiawai_ep01_001",
  "source_branch": "punchline",
  "candidate_type": "punchline",
  "start_time": 59.83,
  "end_time": 68.15,
  "trigger_time": 64.75,
  "summary": "领导夸张担心毒素进脑壳，女主用口水帮他消毒形成笑点。",
  "setup": "领导只有头破皮，却夸张要求医生留下。",
  "punchline": "女主说“来嘛，我帮你消毒”。",
  "payoff": "夸张担心和女主反制动作形成喜剧反差。",
  "evidence": [
    "59.830-63.070 万一感染了，这个毒素进到脑壳头咋办呢？",
    "63.430-64.750 来嘛，我帮你消毒！"
  ]
}
```

## 6. Triggerability Judge

Triggerability Judge 接收 Plot Beat Branch 和 Punchline Branch 的全部候选，输出最终 Top-K triggers 和完整 debug 决策。

### 6.1 可触发判断

保留候选必须满足：

1. 用户在该点有明确表达冲动；
2. 情绪或笑点已经落地，不是 setup；
3. 能明确归入 `爽点`、`甜点`、`泪点`、`笑点` 之一；
4. `trigger_time` 不早于用户理解表达原因的关键台词或动作；
5. 与相邻候选相比，该点是更强的表达释放点。

拒绝候选的常见原因：

- 只是冲突开始；
- 只是冲突升级；
- 只是剧情信息重要，但表达冲动弱；
- 只是惨、哭、危险或压力，没有情感兑现；
- 只是普通帮助、认可、机会，不构成爽点或甜点；
- 类型无法落到四类表达；
- 与更强候选属于同一连续情绪弧。

### 6.2 表达分类

最终只允许四类：

- `爽点`：被压制、羞辱、质疑或不公平对待后，正义方主动反击、打脸、赢回主动权或惩罚恶人；
- `甜点`：暧昧、保护、告白、答应关系、亲密动作或双向在意让关系明显升温；
- `泪点`：亲情、爱情、牺牲、守护、承诺、重逢、告别等情绪兑现；
- `笑点`：punchline、动作反差、误会、尴尬、夸张表达或反应形成明确笑点。

如果候选核心是“震惊”，但不能自然落到四类之一，第一版拒绝，不强行转成笑点。

### 6.3 排序

Judge 对所有可触发候选统一打分和排序，不按 branch 各取固定数量。

建议分数维度：

- `emotion_clarity`：表达类型是否明确；
- `payoff_strength`：情绪释放是否强；
- `context_completeness`：候选范围是否包含必要上下文；
- `timing_quality`：`trigger_time` 是否落在表达刚成立的位置；
- `story_importance`：是否是章节或剧情弧的关键释放；
- `novelty`：是否与已选 trigger 过近或重复。

第一版可让 LLM 给出 `importance_score` 和排序理由，后处理再做硬约束去重。

### 6.4 Top-K 与去重

默认参数：

- `top_k = 4`
- `min_gap_seconds = 20`

规则：

1. 如果高质量候选不足，不强行补满；
2. 同一连续情绪弧只保留最强点；
3. 同类表达在 `min_gap_seconds` 内只保留 `importance_score` 更高者；
4. 不同表达类型但时间很近时，只有两者都很强且语义不同才允许共存；
5. Top-K 应覆盖不同剧情段落，避免一段连续剧情占满全部名额。

### 6.5 时间精修

Judge 可以调整：

- `start_time`：保留理解 trigger 所需的最小上下文；
- `end_time`：保留语义片段结束位置；
- `trigger_time`：表达最适合弹出的唯一时间点。

时间精修原则：

1. `trigger_time` 应落在关键台词、动作或反应成立之后；
2. punchline 的 `trigger_time` 通常落在包袱台词结束或观众刚理解反差的位置；
3. 爽点的 `trigger_time` 通常落在打脸、反击、惩罚动作完成的位置；
4. 甜点的 `trigger_time` 通常落在关系推进被确认的位置；
5. 泪点的 `trigger_time` 通常落在承诺、守护、理解或情感兑现完成的位置。

## 7. 数据输出

### 7.1 最终资产

最终资产文件仍命名为：

```text
expression_triggers.json
```

建议字段：

```json
{
  "video_id": "jialijiawai_ep02",
  "series_id": "jialijiawai",
  "created_at": "2026-06-07T00:00:00Z",
  "expression_triggers": [
    {
      "trigger_id": "et_jialijiawai_ep02_001",
      "start_time": 58.0,
      "end_time": 72.0,
      "trigger_time": 67.0,
      "expression_type": "爽点",
      "importance_score": 0.91,
      "summary": "女主看到儿子被嫂子刁难后直接掀桌反击。",
      "reason": "被欺负的一方当场夺回主动权，解气释放明确，适合作为爽点触发。"
    }
  ]
}
```

最终资产不保存候选和拒绝项。

### 7.2 Debug 资产

Debug 文件命名：

```text
expression_triggers.debug.json
```

建议保留：

- `plot_candidates`
- `punchline_candidates`
- `triggerability_decisions`
- `ranking`
- `rejected_candidates`
- `llm_call`
- `pipeline_config`

示例决策字段：

```json
{
  "candidate_id": "plot_jialijiawai_ep02_004",
  "decision": "reject",
  "reject_reason": "该点核心是突然求婚带来的意外，但第一版最终表达不支持震惊；该片段也没有形成明确笑点、甜点、爽点或泪点。",
  "candidate_type": "reversal"
}
```

## 8. 与现有链路关系

新设计应替代当前 `WorkflowExpressionTriggerPipeline` 的单路候选生成和过滤方式，但保留以下工程资产：

- batch runner 的输入发现、输出目录和跳过逻辑；
- final/debug 双文件输出形式；
- review tool 的 Groundtruth / Prediction 对照能力；
- 现有 gold annotation 作为评估基准；
- frame 抽取和字幕 timeline 工具函数。

需要重写或新增：

- Plot Beat Branch prompt 与 parser；
- Punchline Branch prompt 与 parser；
- Triggerability Judge prompt 与 parser；
- top-k 和去重后处理；
- `trigger_time` 资产格式兼容；
- 评估脚本对 `trigger_time` 的支持。

## 9. 评估方式

第一版继续使用 `data/annotations/expression_trigger_gold` 作为人工标注。

评估维度：

1. 时间命中：预测 `trigger_time` 与 gold `cue_time` 在容忍窗口内；
2. 类型命中：`expression_type` 与 gold `primary_expression` 归一化后一致；
3. 召回率：gold 中有多少被命中；
4. 精确率：预测中有多少是真命中；
5. Top-K 质量：每集前 4 个 trigger 是否覆盖最强表达点；
6. 拒绝合理性：debug 中拒绝的剧情点是否确实不适合触发。

现有 gold 表达可映射为：

```text
爽到了 -> 爽点
笑死   -> 笑点
看哭了 -> 泪点
磕到了 -> 甜点
```

`震惊` 在第一版不作为最终类型。评估时可以单独统计为 unsupported label，不计入四类表达准确率，或在分析报告中标记为“当前标签体系不可覆盖”。

## 10. 典型样例预期

### jialijiawai_ep01

- `67.979 笑点`：应由 Punchline Branch 召回；
- `118.505 爽点`：应由 Plot Beat Branch 召回并由 Judge 保留；
- `186s 泪点`：应由 Judge 拒绝或降低排序，因为只是感谢和善意认可，泪点释放不够强；
- `211.8s 笑点`：可作为弱 punchline 候选，但如果 top-k 竞争失败，可以不进入最终资产。

### jialijiawai_ep02

- `67.023 爽点`：掀桌，应由 Plot Beat Branch 召回；
- `85.117 爽点`：带家具潇洒离开，应由 Plot Beat Branch 召回，Judge 与 67s 做同弧去重或排序；
- `137.208 泪点`：母子桥洞承诺，应由 Plot Beat Branch 召回；
- `208.624 震惊`：第一版最终四类不支持，可拒绝或仅保留在 debug；
- `256.058 甜点`：答应结婚、关系推进，应由 Plot Beat Branch 召回并判为甜点，而不是被女主强势台词抢成爽点。

## 11. 实现决策

当前已确定：

- dual branch；
- Punchline Branch 第一版只抓笑点；
- 最终表达四类：`泪点`、`甜点`、`笑点`、`爽点`；
- 默认 `top_k=4`；
- 默认 `min_gap_seconds=20`；
- 统一使用 `start_time`、`end_time`、`trigger_time`。

代码实现采用以下决策：

1. 新增 `DualBranchExpressionTriggerPipeline`，保留当前 `WorkflowExpressionTriggerPipeline` 作为短期对照和回滚路径；
2. `震惊` gold 在自动评估中作为 unsupported label 单独统计，不计入四类表达准确率分母；
3. 新版 `expression_triggers.json` 立即迁移到 `trigger_time`，评估脚本和 review tool 短期兼容旧输出中的 `cue_time`。

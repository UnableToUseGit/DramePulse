# Expression Trigger 验证观察与阶段结论

更新时间：2026-06-04

## 1. 背景

本轮验证对象是 `output/workflow_expression_trigger` 下的 expression trigger 识别结果，以及人工标注目录：

```text
data/annotations/expression_trigger_gold
```

当前前端情绪按钮只承载四类基础表达：

```text
爽点
笑点
甜点
泪点
```

本轮讨论暂不处理 `震惊` 标签和四按钮体系不一致的问题。

评估命令：

```bash
PYTHONPATH=. python scripts/evaluate_expression_trigger_annotations.py \
  --annotation-dir data/annotations/expression_trigger_gold \
  --algorithm-output-root output/workflow_expression_trigger \
  --report-path output/workflow_expression_trigger_annotation_eval/report.json \
  --tolerance-sec 10
```

修正 `tianxia_diyi_wanku_ep01` 的人工标注后，当前评估结果：

```text
episodes=10
gold=29
predictions=19
matched=12
recall=0.413793
precision=0.631579
expression_accuracy_on_matches=0.75
```

如果只看有 gold 的 7 集，不把 `yunmiao_1_ep01/02` 空 gold 集的预测计入 precision，当前 precision 约为 `0.75`。但 `yunmiao_1_ep01/02` 实际上应保留为 hard negative，因为它们前两集以剧情铺垫为主，确实没有足够强的四类按钮触发点。

## 2. 当前观察

### 2.1 workflow 能抓住部分剧情型强高光

当前 workflow 对完整剧情 payoff 有一定能力。例如：

- `beiwang_ep01`：讨薪翻门发现门没锁；
- `beiwang_ep01`：母子电话中“不回家”到“年三十一定回家”的亲情兑现；
- `jiali_jiawai_ep01`：男主替女主出气，领导当场取消处分者评优；
- `tianxia_diyi_wanku_ep01`：男主扮猪吃老虎，暗中出手秒杀蛮人。

这说明 `setup -> turning point -> payoff` 作为剧情型候选识别框架是有价值的。

### 2.2 第一轮候选召回仍然太少

当前低 recall 的主要原因不是 cue time 只差几秒，而是很多 gold 点在第一轮候选中根本不存在。

典型例子：

- `nanian_dongzhi_ep01`：gold 有 8 个，算法候选只有 2 个；
- `beiwang_ep01`：gold 有 6 个，算法候选只有 4 个；
- `jiali_jiawai_ep02`：gold 有 5 个，算法候选只有 3 个。

将评估容忍窗口从 10 秒扩大到 20 秒，recall 只从约 `0.414` 提升到约 `0.483`，说明主问题不是简单的时间偏移。

### 2.3 剧情 payoff 和 punchline 笑点是不同召回对象

当前 workflow 更擅长找剧情 interval，但短剧中的许多笑点不是完整剧情 payoff，而是单句台词或短对话包袱。

典型 punchline：

- `过年好`
- `甘蔗`
- `做一次少一次`
- `准备后事`

这些点的特征是：

- 情绪释放发生在一句台词或一个短回应上；
- 不一定需要完整剧情弧线；
- cue time 往往应放在 punchline 字幕结束附近；
- 如果强行放进剧情 payoff 框架，模型容易把它压缩成一个大的剧情段，并误判成 `爽点` 或 `甜点`。

因此，后续不能只靠剧情型候选枚举，需要单独增加 `punchline_candidates` 召回通道。

### 2.4 结构成立不等于情绪强烈

`yunmiao_1_ep01` 是本轮最重要的 hard negative。

算法识别出两个点：

1. 女主说出周老爷只有见到自己才会咽气，仆人态度转变，请她进门；
2. 周家儿子哭诉父亲病重三个月，自己请遍相关的人仍然无效。

这两个点都可以被解释成：

```text
setup -> turning point -> payoff
```

但实际观看时情绪不强。

第一个点不是强爽点，因为：

- 阻拦者不是强反派，只是在履行职责；
- 女主没有真正打脸恶人，只是证明自己知道内情；
- payoff 只是“被允许进门”，结果价值较低；
- 没有强压抑积累、地位翻转或惩罚。

第二个点不是强泪点，因为：

- 观众和父子关系尚未建立足够情感连接；
- 这里主要是在说明困境，而不是情绪释放；
- 没有牺牲、重逢、告别、原谅、心愿完成等强 payoff；
- 哭诉、病重、痛苦本身不等于泪点。

结论：`has_payoff_structure` 只是必要条件，不是充分条件。算法还需要判断 `button_worthy_intensity`，也就是这个点是否真的强到值得前端弹按钮。

### 2.5 类型判定需要更贴近用户即时反应

`nanian_dongzhi` 中，模型把部分女主调戏男主的台词判断为 `爽点` 或 `甜点`，但人工感受是 `笑点`。

这说明四个按钮不是纯剧情功能分类，而是用户即时反应分类。

当片段同时具备暧昧、反击、调侃时，应按观众最可能的即时反应归类：

- 主要想笑：`笑点`
- 主要嗑关系升温：`甜点`
- 主要感到打脸解气：`爽点`
- 主要被情感释放打动：`泪点`

例如带有暧昧关系推进的调侃台词，如果观众最直接的反应是“好笑”，应优先归为 `笑点`。

### 2.6 yunmiao 暴露了“重要剧情不等于互动高光”

`yunmiao_1_ep01/02` 的 gold 为空不是因为漏标，而是因为前两集确实偏铺垫，没有强四点。

算法在这两集上输出了：

- `yunmiao_1_ep01`：一个弱爽点、一个弱泪点；
- `yunmiao_1_ep02`：一个弱泪点。

这些误报说明模型容易把以下内容误判成互动高光：

- 重要剧情推进；
- 人物困境；
- 病重、哭诉、无力感；
- 小型身份确认；
- 铺垫性反转。

后续 review 阶段需要明确拒绝这些“有剧情意义但不够强”的点。

## 3. 当前主要结论

### 3.1 当前算法不是完全失效，而是目标粒度还不够准

workflow 已经能识别部分剧情型强高光，但它当前更像“剧情高光识别”，还不是稳定的“前端按钮 cue 识别”。

前端按钮 cue 的要求更窄：

- 要有明确即时反应；
- 要足够强；
- 要在合适时间点触发；
- 要控制数量；
- 要允许没有触发点的剧集输出 0。

### 3.2 低 recall 的优先原因是候选枚举不足

很多 missed 点不是被 review 错杀，而是在 `expression_candidates` 里就没有出现。

因此，下一步优先改 candidate generation，而不是继续调最终后处理。

### 3.3 需要从单一路径改成多通道候选召回

建议下一阶段 candidate generation 至少拆成三类：

```text
plot_payoff_candidates
  剧情型爽点 / 甜点 / 泪点 / 笑点

punchline_candidates
  台词型笑点和短对话包袱

visual_candidates
  低字幕密度下的视觉动作、表演、亲密、战斗、反应镜头 payoff
```

三类候选进入同一个 review 和 postprocess 阶段。

### 3.4 review 阶段需要加入强度校准

review 不应只判断“能否解释成某类 payoff”，还要判断：

```text
这个点是否强到值得前端弹按钮？
```

建议增加独立字段或判定维度：

- `button_worthy_intensity`
- `viewer_reaction_strength`
- `is_button_worthy`

其中 `confidence` 表示模型对判断的置信度，不应替代强度。一个点可以让模型很确定它是弱铺垫，但它仍不应该进入最终 cue。

### 3.5 negative case 应进入 prompt 和评估

`yunmiao_1_ep01/02` 应作为 hard negative 保留。

prompt 中应加入反例规则：

- 病重不等于泪点；
- 哭诉不等于泪点；
- 被允许进门不等于爽点；
- 证明自己知道内情不等于打脸；
- 重要剧情推进不等于互动高光；
- 没有明确情绪释放时应 reject。

## 4. 下一步算法方向

建议将 expression trigger workflow 调整为：

```text
候选召回
  1. plot_payoff_candidates：剧情型候选，保留 setup -> turning point -> payoff 框架
  2. punchline_candidates：字幕台词型笑点候选，以 subtitle turn 为核心
  3. visual_candidates：低字幕密度视觉候选，使用密集帧辅助召回

候选复核
  1. 判断是否属于四类按钮
  2. 判断是否 button-worthy
  3. 校准 primary_expression
  4. 拒绝铺垫、弱反转、普通悲伤信息、普通剧情推进

后处理
  1. 合并同一情绪弧
  2. 保留独立 punchline
  3. 控制数量
  4. 输出 cue_time、duration、emotion_type、confidence、intensity
```

## 5. 当前优先级

下一阶段建议优先级：

1. 增加 `punchline_candidates`，提高台词型笑点召回；
2. 在 review 中加入 `button_worthy_intensity` 或等价强度判定；
3. 用 `yunmiao_1_ep01/02` 作为 hard negative 改进拒绝规则；
4. 调整四类按钮的分类优先级，使其以用户即时反应为准；
5. 再观察 cue_time 偏移和最终排序问题。

核心结论：

```text
不能只问“这里有没有剧情 payoff”，还要问“观众会不会真的在这里想点按钮”。
```

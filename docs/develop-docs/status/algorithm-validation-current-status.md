# 算法验证闭环现状与问题记录

更新时间：2026-06-03

## 1. 当前目标

当前算法开发重点不是直接做线上策略，而是先建立验证闭环：

```text
数据集 -> 算法输出 -> 前端观察 -> 人工标注/反馈 -> 评估与问题归因 -> 算法迭代
```

现阶段主要验证对象是短剧情绪表达触发点，也就是在播放过程中适合让用户低摩擦表达“爽到了、磕到了、看哭了、笑死”的剧情点。

当前重点测试剧集：

- `beiwang` 前 2 集
- `nanian_dongzhi` 前 2 集
- `tianxia_diyi_wanku` 前 2 集

这三部剧的类型差异比较明显，适合作为第一轮算法验证集：

- `beiwang`：现实题材，亲情/返乡/打工人情绪明显；
- `nanian_dongzhi`：台词和关系推进较强；
- `tianxia_diyi_wanku`：偏严肃古装，表达点密度较低。

## 2. 当前已有能力

### 2.1 数据集与观察工具

当前使用的数据集目录：

```bash
/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm
```

当前用于观察算法结果的前端服务：

```bash
python scripts/serve_algorithm_review_tool.py \
  --data-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/workflow_expression_trigger \
  --port 8783
```

相关工具：

- `apps/algorithm-review-tool/`：观察 expression trigger 结果；
- `apps/annotation-tool/`：人工标注触发点；
- `apps/subtitle-density-tool/`：观察字幕密度分段；
- `scripts/evaluate_expression_trigger_annotations.py`：评估预测结果和人工标注；
- `scripts/analyze_danmaku_expression_triggers.py`：基于弹幕做离线辅助分析。

### 2.2 表达类型 taxonomy

当前只保留四类基础表达点：

```text
爽到了
磕到了
看哭了
笑死
```

已经删除或暂不考虑的类型包括：

- 震惊
- 燃起来了
- 气死了
- 心疼
- 紧张
- 站主角
- 想看后续
- 剧集喜爱
- 共鸣了
- 吐槽
- 角色魅力

目前判断方向是：宁可先把 taxonomy 收窄，保证每一类都能被清楚定义和验证。

### 2.3 当前 expression trigger workflow

当前主流程文件：

- `pipelines/workflow_expression_trigger_detection.py`
- `scripts/run_workflow_expression_trigger_detection_batch.py`

运行示例：

```bash
python scripts/run_workflow_expression_trigger_detection_batch.py \
  --data-root /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm \
  --output-root output/workflow_expression_trigger \
  --series-id beiwang nanian_dongzhi tianxia_diyi_wanku \
  --episode-id ep01 ep02 \
  --sample-interval-sec 10 \
  --visual-candidate-window-sec 10 \
  --visual-window-sample-interval-sec 1 \
  --visual-window-max-frames 80 \
  --frame-max-height 512 \
  --filter-frame-interval-sec 2 \
  --filter-candidate-context-sec 2 \
  --filter-max-frames 100 \
  --final-same-expression-gap-sec 30 \
  --final-min-intensity 0.6 \
  --final-min-confidence 0.72 \
  --final-max-triggers 4 \
  --force
```

流程分三步：

1. 候选生成
   - 输入：全量字幕 + 全局抽帧；
   - 抽帧：默认每 10 秒 1 帧；
   - 视觉补召回：按固定窗口检测低台词密度区间，默认窗口长度 10 秒；对低台词密度窗口额外密集采帧，默认每 1 秒 1 帧，最多 80 帧；
   - 图片高度：`frame_max_height=512`；
   - 目标：高召回，尽量覆盖可能的情绪点；
   - 输出：`expression_candidates`。

2. 候选复核
   - 输入：全量字幕 + 候选列表 + 候选窗口局部抽帧；
   - 局部抽帧：候选窗口前后扩 2 秒，默认每 2 秒 1 帧；
   - 最大局部帧数：`filter_max_frames=100`；
   - 输出：`candidate_decisions` 和 `expression_triggers`。

3. 最终后处理
   - 过滤低强度/低置信点；
   - 对同类相邻 trigger 做去重择优；
   - 默认最终最多保留 4 个 trigger；
   - 目标是让最终结果更像播放器里真的要弹出的互动点，而不是所有可能成立的情绪片段。

### 2.4 纯文本 baseline

当前也保留纯文本版本：

- `pipelines/text_expression_trigger_detection.py`
- `scripts/run_text_expression_trigger_detection_batch.py`

观察结论：

- 纯文本在 `beiwang`、`nanian_dongzhi` 上效果比预期好；
- 对字幕能表达清楚的剧情点，定位精度可以较高；
- 对视觉笑点、表演反应、无对白动作段落，仍然容易漏掉。

### 2.5 章节划分算法

已经从 `story-navigation` worktree 复制章节划分相关文件到当前目录，便于后续一起开发：

- `pipelines/story_chapter_generation.py`
- `pipelines/story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation.py`
- `scripts/run_story_chapter_generation_batch.py`
- `scripts/run_story_chapter_generation_multimodal.py`
- `scripts/run_story_chapter_generation_multimodal_batch.py`
- `scripts/story_chapter_viewer_server.py`
- `apps/story-chapter-viewer/`

章节算法当前有两版：

- text-only：基于字幕和转写；
- multimodal：基于字幕 + 视频帧。

它的作用暂时不是直接生成 expression trigger，而是后续可以为 trigger 算法提供剧情结构上下文，例如“当前候选点属于哪一个章节/剧情段”。

## 3. 当前主要观察

### 3.1 候选生成总体可用，但剧种差异明显

已观察到：

- `beiwang_ep01`
- `beiwang_ep02`
- `nanian_dongzhi_ep01`
- `nanian_dongzhi_ep02`

这些剧集的候选生成基本能覆盖人工认为的重要点。

但：

- `tianxia_diyi_wanku_ep01`
- `tianxia_diyi_wanku_ep02`

候选生成效果明显不如前两类剧。

初步判断不是简单的算法失效，而是题材分布不同：

- `tianxia_diyi_wanku` 前两集偏严肃；
- `ep01` 只有一个笑点和一个不典型爽点；
- `ep02` 基本没有明确表达触发点；
- `ep01` 的爽点是“男主扮猪吃老虎，前面看起来纨绔，实际武功极高，秒杀蛮人”，这不是典型现代短剧的压抑后打脸，而是隐藏实力/身份能力反差型爽点。

因此需要让算法允许低密度剧集输出很少甚至 0 个 trigger，同时在 `爽到了` 的定义中谨慎覆盖“隐藏实力/扮猪吃老虎/被低估后展现压倒性能力”。

### 3.2 二阶段 filter 曾经不够有效

在旧输出中，二阶段 filter 的通过率偏高：

```text
beiwang_ep01                 candidates= 6  triggers= 6  pass_rate=1.00
beiwang_ep02                 candidates= 5  triggers= 5  pass_rate=1.00
nanian_dongzhi_ep01          candidates= 7  triggers= 6  pass_rate=0.86
nanian_dongzhi_ep02          candidates= 6  triggers= 5  pass_rate=0.83
tianxia_diyi_wanku_ep01      candidates= 8  triggers= 6  pass_rate=0.75
tianxia_diyi_wanku_ep02      candidates= 3  triggers= 1  pass_rate=0.33
```

问题表现：

- filter 更像是润色候选，而不是真正审稿；
- rejected candidate 不可见，难以 debug；
- 相邻候选容易全部进入最终 trigger。

已经做的改动：

- filter prompt 要求输出 `candidate_decisions`；
- 每个 candidate 都必须有 `keep/reject` 和 `decision_reason`；
- batch 输出保存 `candidate_decisions`；
- 增加 deterministic post-processing。

后续需要重新跑一批结果，验证 filter 是否真的开始 reject，以及 reject reason 是否有分析价值。

### 3.3 最终 trigger 需要密度控制

旧的 `beiwang_ep01` 输出中出现明显相邻密集问题：

```text
36.5 - 47.6    笑死
49.0 - 73.8    看哭了

147.2 - 187.9  看哭了
195.1 - 243.3  看哭了
254.9 - 266.9  看哭了
275.2 - 295.3  笑死
```

其中 `147.2-266.9` 的三个 `看哭了` 本质上属于同一条“亲情/回家”情绪弧线：

1. 儿子骗母亲说不回家，母亲失落；
2. 儿子改口说一定回家，母亲开心破防；
3. 同伴追问想不想回家，说出漂泊思乡。

最像真正 interaction trigger 的是第 2 个，因为它是前面失落铺垫后的情绪兑现。第 1 个更像 setup，第 3 个更像 aftermath。

这说明：

- candidates 可以密集；
- final triggers 必须稀疏；
- 同一情绪弧线只保留最强 payoff 点。

已经做的改动：

- 默认过滤 `intensity < 0.6` 或 `confidence < 0.72` 的弱点；
- 同一 `primary_expression` 且相邻小于 30 秒时择优保留；
- 默认最终最多保留 4 个 trigger。

这些阈值还需要继续基于人工标注和前端观察调整。

### 3.4 成本和延迟仍然偏高

旧输出中 `beiwang_ep01` 的一次 workflow 调用成本较高：

```text
candidate_generation:
  image_count: 31
  elapsed_sec: 35.702
  total_tokens: 10159

candidate_filtering:
  image_count: 100
  elapsed_sec: 146.936
  total_tokens: 24200
```

这说明：

- 二阶段局部抽帧虽然提高了视觉信息量，但成本明显增加；
- `filter_max_frames=100` 可能偏高；
- 后续如果要批量跑更多剧集，需要考虑更便宜的候选复核方案。

可能方向：

- 对候选窗口抽帧数量做动态控制；
- 只对字幕低密度或视觉依赖候选加密抽帧；
- 先用 text-only/轻量模型初筛，再让 MLLM 复核少量候选；
- 用章节划分结果减少候选上下文长度。

## 4. 已经解决或阶段性解决的问题

### 4.1 时间单位混淆

之前模型把字幕时间如 `[04:35.280]` 理解成 `435.28` 秒，导致输出超过视频时长。

当前已经统一成秒数格式：

```text
[275.280-281.300] subtitle text
```

并在 prompt 中明确：

```text
All subtitle timestamps and output times are plain seconds, not MM:SS or HH:MM:SS.
```

### 4.2 原生分辨率抽帧成本过高

当前抽帧已经通过 `frame_max_height=512` 控制图片高度，降低 MLLM 输入成本。

### 4.3 LLM 调用调试信息不足

当前输出中已经记录 LLM 调用诊断信息：

- provider
- model
- max_tokens
- image_count
- frame_timestamps_count
- prompt char count
- elapsed_sec
- usage tokens
- request_id
- status

失败时也会写 failure diagnostics。

### 4.4 弹幕输入来源不完整

之前弹幕从 `douyin.json` 读取，数据不全。当前已经优先支持从数据集根目录下的弹幕 CSV 读取。

## 5. 当前待解决问题

### 5.1 `tianxia_diyi_wanku` 的低密度剧集处理

需要明确：

- 允许一集输出 0 个 trigger；
- 不为了凑数量硬找笑点或爽点；
- 对“隐藏实力/扮猪吃老虎”型爽点做更精确定义；
- 避免把普通展示能力误判为爽点。

### 5.2 filter 阶段是否真的开始工作

需要重新跑最新 workflow，观察：

- `candidate_decisions` 是否有足够 reject；
- reject reason 是否符合人工理解；
- final trigger 数量是否明显下降；
- 是否误删人工标注点。

### 5.3 后处理阈值需要用标注集校准

当前阈值是经验值：

```text
final_same_expression_gap_sec = 30
final_min_intensity = 0.6
final_min_confidence = 0.72
final_max_triggers = 4
```

需要基于人工标注评估：

- 是否过度删除；
- 是否仍然过密；
- 不同剧种是否需要不同阈值；
- 是否应该用 episode duration 动态决定 `final_max_triggers`。

### 5.4 前端观察信息还不够完整

当前 review tool 已能观察 trigger 和 reason，但后续应该继续增强：

- 展示 `expression_candidates`；
- 展示 `candidate_decisions`；
- 展示 rejected candidates；
- 展示 post-processing 前后的 trigger 对比；
- 标出人工标注点和预测点的匹配关系。

这样才能判断问题发生在：

```text
candidate generation -> filter decision -> post-processing -> final output
```

哪一个环节。

### 5.5 章节划分还没有接入 trigger workflow

章节算法已经复制到当前目录，但还没有和 expression trigger workflow 集成。

潜在价值：

- 给 trigger 候选提供章节上下文；
- 帮助判断某个点是 setup、payoff 还是 aftermath；
- 减少同一剧情弧线重复输出多个 trigger；
- 给前端提供剧情导航和触发点解释。

当前不建议立即大规模重构，但可以先把章节结果作为可选输入接进 workflow。

## 6. 建议的下一步

短期优先级：

1. 用最新 workflow 重新跑三部剧前 2 集。
2. 对比 `expression_candidates`、`candidate_decisions`、`expression_triggers`。
3. 用 review tool 检查：
   - 是否仍然密集；
   - 是否有明显误删；
   - `tianxia_diyi_wanku_ep02` 是否能正确输出 0 个或接近 0 个点。
4. 跑人工标注评估脚本，确认分数变化。
5. 根据观察调后处理阈值。

中期方向：

1. 让 review tool 显示 candidate decision 和 rejected candidates。
2. 将章节划分结果作为 trigger workflow 的可选上下文。
3. 为不同剧种记录失败案例和 prompt 调整原因。
4. 梳理算法输出契约，避免后续多个算法并入时格式分裂。

## 7. 当前状态总结

当前 pipeline 已经从“一步式 MLLM 识别”进化为：

```text
高召回候选生成
  -> 候选级结构假设
  -> 局部帧复核
  -> candidate keep/reject 决策
  -> final trigger 后处理
  -> 前端观察和人工反馈
```

这个方向是可继续迭代的，但还没有达到稳定算法状态。当前最核心的问题不是单个 prompt，而是：

- 不同剧种 trigger 密度差异大；
- candidates 和 final triggers 的职责需要严格区分；
- filter 阶段必须真正 reject；
- final output 必须符合播放器交互密度，而不是算法候选密度。

## 8. 2026-06-03 workflow 契约改进

本轮围绕 action rail 情绪共鸣按钮的前端需求，对 workflow 输出契约做了收敛。

核心变化：

1. 统一四类算法与前端 taxonomy：
   - `爽点`
   - `笑点`
   - `甜点`
   - `泪点`

2. 保留旧表达别名兼容：
   - `爽到了 -> 爽点`
   - `笑死 -> 笑点`
   - `磕到了 -> 甜点`
   - `看哭了 -> 泪点`

3. 引入更清晰的时间概念：
   - `story_interval_start` / `story_interval_end`：剧情理解区间；
   - `payoff_time`：情绪兑现点，后续作为算法评估主目标；
   - `ui_trigger_time`：前端按钮出现时间，由产品包装策略生成。

4. workflow 结果新增 `resonance_cues`：

```json
{
  "cue_id": "res_demo_ep01_001",
  "source_trigger_id": "et_demo_ep01_001",
  "ui_trigger_time": 41.5,
  "duration_sec": 6.0,
  "emotion_type": "泪点",
  "label": "泪目了",
  "icon": "tear",
  "feedback_text": "你也泪目了"
}
```

5. 候选生成阶段新增低字幕密度视觉窗口和密集采帧：
   - 基于固定时间窗口内的字幕覆盖率发现 `visual_candidate_windows`；
   - 对这些窗口额外按 `visual_window_sample_interval_sec` 密集采帧；
   - 全局 overview 帧会先排除 `visual_candidate_windows` 内的时间点，再和视觉密集帧合并去重后输入候选生成模型；
   - `max_frames` 控制视觉窗口外的全局剧情 overview 帧，`visual_window_max_frames` 单独控制视觉补召回帧预算；
   - 这些窗口不直接判定为高光，只为模型提供更多视觉证据；
   - 目标是补召回无对白或低对白的动作爽点、视觉笑点、亲密动作和哭泣/拥抱等 payoff。

6. 评估脚本支持新标注格式：
   - gold 可使用 `payoff_time`；
   - gold 可提供 `payoff_window`；
   - prediction 优先使用 `payoff_time`，兼容旧 `cue_time`；
   - `ui_trigger_time` 不参与算法主评估。

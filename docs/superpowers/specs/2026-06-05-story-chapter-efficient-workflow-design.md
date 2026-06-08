# Story Chapter 高效 Workflow 设计

更新时间：2026-06-05

## 1. 背景

当前 `pipelines/story_chapter` 的章节划分主要依赖两类 baseline：

- `baseline_text.py`：只把字幕时间线交给 LLM，让模型直接输出章节；
- `baseline_mllm.py`：按固定间隔抽帧，将大量视频帧和字幕一起交给 MLLM，让模型直接输出章节。

这类方式适合快速验证方向，但存在两个明显问题：

1. **成本高**：MLLM 需要处理全片抽样帧，短剧数量扩大后成本不可控；
2. **稳定性差**：当传输帧数达到 120 帧以上时，API 容易超时，导致批处理不可稳定运行。

后续章节划分应从“完全依赖 MLLM 一次性判断”调整为“规则召回候选边界 + 文本语义评分 + 小窗口 MLLM 选择”的 workflow。MLLM 仍然参与最终判断，但只处理候选边界附近的关键帧，并同时接收全量字幕上下文，以保留全局剧情理解能力。

## 2. 目标

本次设计目标是定义新的 `Story Chapter Workflow`，用于替代全量 MLLM baseline 作为后续主要开发方向。

需要达成：

1. 降低 MLLM 输入帧数，避免 120 帧以上请求导致超时；
2. 保留 MLLM 对视觉转场、无字幕段、动作段的判断能力；
3. 让章节边界选择基于候选边界，而不是让模型自由生成任意时间点；
4. 让最终 `story_chapters.json` 仍满足播放器消费要求：完整覆盖全片、无 gap、无 overlap、标题短且可展示；
5. 让中间产物可解释，方便调试候选边界为什么被召回、为什么被选中或拒绝；
6. 为后续批量评测和人工 review 工具保留稳定数据结构。

## 3. 非目标

本次 workflow 不解决以下问题：

- 不做用户互动触发点识别；
- 不把 `Expression Trigger` 或高光点直接当作章节边界；
- 不使用 cue word、speaker change、highlight signal 作为候选召回信号；
- 不引入复杂机器学习训练；
- 不做个性化章节导航；
- 不改变播放器端消费的最终章节字段含义；
- 不删除现有 `baseline_text.py` 和 `baseline_mllm.py`，它们继续作为对照 baseline。

## 4. 总体流程

推荐流程：

```text
transcription + scene_detection + video_metadata
        ↓
rule candidate recall
  scene_boundary / long_pause / dialogue_density_change
        ↓
text LLM topic shift scoring
        ↓
candidate merge + top-N pruning
        ↓
MLLM selector
  full subtitles + candidate-local frames
        ↓
postprocess validation
        ↓
story_chapters.json
```

核心取舍：

- 规则模块负责高召回、低成本地提出候选边界；
- text LLM 负责判断候选点前后是否存在剧情话题变化；
- MLLM selector 负责从候选边界中选择最终章节边界，并生成标题摘要；
- 程序化后处理负责契约兜底，保证输出可被播放器稳定消费。

## 5. 候选边界召回

候选召回阶段只使用三类规则信号：

1. `scene_boundary`
2. `long_pause`
3. `dialogue_density_change`

### 5.1 Scene Boundary

每个镜头边界都是弱候选。召回时记录：

- boundary time；
- 前后 scene id；
- 前后 scene 时长；
- 是否靠近字幕起止点。

scene boundary 的作用是为 MLLM selector 提供视觉转场附近的可选切点，但不能直接等同于章节边界。

### 5.2 Long Pause

基于字幕句子之间的 gap 召回边界：

```text
gap = next_utterance.start_time - current_utterance.end_time
```

建议初始阈值：

- `gap >= 1.2s`：召回；
- `gap >= 2.0s`：提高分数；
- `gap >= 4.0s`：强候选。

候选时间优先取下一句字幕的 `start_time`，如果附近存在 scene boundary，则吸附到最近 scene boundary。

### 5.3 Dialogue Density Change

使用滑动窗口计算候选点前后的字幕密度变化。

建议窗口：

```text
before_window = [t - 12s, t)
after_window = [t, t + 12s)
```

指标：

- 字符数 / 秒；
- utterance 数 / 秒；
- 平均句长。

如果前后密度变化超过阈值，则召回候选。该信号用于识别“密集对话进入沉默”“铺垫进入争执”“解释进入行动”等节奏变化。

### 5.4 候选合并

规则召回后会产生相近候选。需要先合并：

- 距离小于 `3s` 的候选合并为一个；
- 合并后保留全部 signals；
- 时间优先吸附到 scene boundary；
- 证据保留每类信号的关键数据。

候选结构：

```json
{
  "candidate_id": "bc_007",
  "time": 42.0,
  "rule_score": 0.56,
  "signals": ["scene_boundary", "long_pause"],
  "evidence": {
    "gap_seconds": 1.8,
    "before_density": 5.4,
    "after_density": 1.2
  }
}
```

## 6. Text LLM Topic Shift Scoring

`topic_shift` 直接由 text LLM 判断。短剧字幕较短，因此使用 text LLM 做候选点语义评分是可接受的，并且成本远低于全量 MLLM。

### 6.1 输入

一次请求批量传入候选点。每个候选点包含：

- `candidate_id`
- `time`
- `signals`
- 候选点前 `5-8` 句字幕；
- 候选点后 `5-8` 句字幕。

### 6.2 输出

```json
{
  "topic_shift_reviews": [
    {
      "candidate_id": "bc_007",
      "topic_shift_score": 0.82,
      "boundary_type": "身份揭露后进入反应段",
      "reason": "前文围绕男主身份质疑，后文转为众人对身份揭露的反应。"
    }
  ]
}
```

text LLM 不负责生成最终章节，也不负责自由新增边界。它只对候选点前后是否属于同一剧情段进行评分。

## 7. MLLM Selector

MLLM selector 是最终边界选择器。它使用全量字幕理解全局剧情，同时只接收候选边界附近的小窗口帧，避免全片 120 帧以上输入。

### 7.1 输入

MLLM selector 输入包含：

- 视频元信息；
- 全量字幕时间线；
- top-N 候选边界；
- 每个候选边界附近的关键帧。

建议 top-N：

```text
12 到 16 个候选边界
```

每个候选边界建议取：

```text
t - 1s
t
t + 1s
```

因此单次 MLLM 请求通常控制在 36 到 48 帧以内。

输入示例：

```json
{
  "video_id": "demo_ep01",
  "duration_seconds": 180.0,
  "full_utterance_timeline": [
    {
      "utterance_id": "u_001",
      "start_time": 1.0,
      "end_time": 2.4,
      "text": "你根本不知道他是谁。"
    }
  ],
  "boundary_candidates": [
    {
      "candidate_id": "bc_007",
      "time": 42.0,
      "score": 0.81,
      "signals": ["scene_boundary", "long_pause", "llm_topic_shift"],
      "topic_shift_reason": "身份质疑转入身份揭露后的反应。",
      "frame_timestamps_seconds": [41.0, 42.0, 43.0]
    }
  ],
  "constraints": {
    "min_chapter_seconds": 12,
    "target_chapter_seconds": 35,
    "max_chapter_seconds": 75,
    "max_chapters": 8
  }
}
```

### 7.2 选择规则

MLLM selector 必须遵守：

1. 只能从给定 `boundary_candidates` 中选择内部章节边界；
2. 第一章固定从 `0.0` 开始；
3. 最后一章固定到 `duration_seconds` 结束；
4. 不允许 gap；
5. 不允许 overlap；
6. 不应把一次连续对话中过近的多个候选点都选中；
7. 标题应是短中文剧情标签，适合播放器时间轴展示；
8. 摘要应是一句事实性中文描述。

如果 MLLM 判断候选集缺少必要边界，只能通过 warning 表达：

```json
{
  "type": "missing_boundary",
  "message": "42s 到 120s 内存在明显剧情转场，但候选边界不足。"
}
```

### 7.3 输出

```json
{
  "chapters": [
    {
      "start_time": 0.0,
      "end_time": 42.0,
      "end_boundary_candidate_id": "bc_007",
      "title": "身份遭疑",
      "summary": "众人质疑男主身份，冲突逐步升级。",
      "importance": 0.72
    },
    {
      "start_time": 42.0,
      "end_time": 180.0,
      "end_boundary_candidate_id": null,
      "title": "继承人曝光",
      "summary": "男主真实身份揭开，局势发生反转。",
      "importance": 0.91
    }
  ],
  "rejected_candidates": [
    {
      "candidate_id": "bc_009",
      "reason": "只是同一争执中的短暂停顿，不构成新章节。"
    }
  ],
  "warnings": []
}
```

## 8. Postprocess Validation

MLLM 输出后必须做程序化校验。

校验规则：

1. `chapters` 必须非空；
2. 第一章 `start_time` 必须为 `0.0`；
3. 最后一章 `end_time` 必须为 `duration_seconds`；
4. 相邻章节必须连续；
5. 不允许 overlap；
6. 内部边界必须来自候选点；
7. `end_time` 必须大于 `start_time`；
8. `importance` 必须在 `0..1`；
9. `title` 和 `summary` 不得为空。

如果输出不合法：

- 记录 warning；
- 尝试修复可修复问题，例如浮点误差、最后一章结束时间；
- 无法修复时 fallback 到规则 selector，生成可用但质量较低的章节。

### 8.1 规则 Selector Fallback

fallback 只用于保证批处理不中断，不作为主要质量路径。

fallback 策略：

1. 从已合并候选中按最终候选分数排序；
2. 过滤会导致章节短于 `min_chapter_seconds` 的候选；
3. 依次选择不冲突的高分候选，直到达到 `max_chapters` 或没有合格候选；
4. 如果没有任何合格候选，则输出一个覆盖全片的章节；
5. fallback 生成的章节标题使用 `"剧情片段"` 加序号，摘要使用 `"该片段为自动兜底生成，需人工复核。"`；
6. payload 必须写入 warning，说明触发 fallback 的原因。

fallback 输出仍必须满足完整覆盖、无 gap、无 overlap。

## 9. 输出 Artifact

最终仍写入：

```text
<output_root>/<video_id>/story_chapters.json
```

建议增加 workflow 中间产物字段：

```json
{
  "video_id": "demo_ep01",
  "generation_mode": "workflow_candidate_mllm_selector",
  "video_metadata": {
    "duration_seconds": 180.0
  },
  "utterances": [],
  "boundary_candidates": [],
  "mllm_selector_result": {},
  "selected_chapters": [],
  "story_chapters": [],
  "warnings": []
}
```

前端和已有消费者继续读取 `story_chapters`。调试工具和评测脚本可以读取 `boundary_candidates`、`selected_chapters` 和 `warnings`。

## 10. 测试与验收

### 10.1 单元测试

需要覆盖：

1. scene boundary 候选召回；
2. long pause 候选召回；
3. dialogue density change 候选召回；
4. 相近候选合并；
5. topic shift 解析；
6. MLLM selector 输出解析；
7. postprocess 修复浮点误差；
8. 非法输出 fallback；
9. 最终章节完整覆盖全片；
10. 最终章节无 gap、无 overlap。

### 10.2 Smoke Test

使用一条短剧样例跑完整 workflow，检查：

- MLLM 输入帧数明显少于全量 `baseline_mllm`；
- 输出章节数量合理；
- 每个章节 title 适合时间轴展示；
- `warnings` 对异常情况有明确解释。

### 10.3 验收标准

第一版完成后应满足：

1. 不再需要向 MLLM 传输全片 120 帧以上；
2. MLLM selector 能看到全量字幕，保留全局剧情上下文；
3. 内部边界只能来自候选边界；
4. 输出 `story_chapters` 可被现有 story navigation 消费；
5. 对候选召回、选择、拒绝和后处理都有可检查中间结果。

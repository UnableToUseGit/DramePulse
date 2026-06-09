# 算法 Pipeline 目录重构设计

更新时间：2026-06-04

## 1. 背景

当前 `pipelines/` 和 `scripts/` 已经支撑了多轮算法验证，但目录结构仍保留了探索期特征：

- 单个 pipeline 文件承担过多职责，尤其是 `workflow_expression_trigger_detection.py` 已经混合了类型定义、prompt、候选生成、候选复核、后处理、前端 cue 映射和执行编排；
- 多个脚本之间存在复用关系，例如 batch 脚本中包含数据集发现、LLM client 构建、输出写入、失败诊断等公共逻辑；
- 旧版 `highlight` / `interaction plan` 实现仍留在目录中，和当前已确定的算法方向混在一起；
- 后续 expression trigger 需要增加 `punchline_candidates`、`button_worthy` 等能力，现有单文件结构会让改动风险继续上升。

本次重构目标是在不改变算法行为的前提下，先建立稳定、可扩展、可测试的算法目录结构，为下一阶段算法迭代做准备。

## 2. 重构目标

本次重构需要达成以下目标：

1. 将已确定要实现的三条算法线纳入正式目录结构：
   - `expression trigger`
   - `story chapter`
   - `inner voice danmaku`
2. 删除不再维护的旧实现：
   - `highlight_candidate_generation`
   - `highlight_recognition`
   - `interaction_plan_generation`
3. 将模型调用适配层保留为独立 `client` 目录；
4. 将无业务归属的字幕、抽帧、采样、数据集发现、artifact 写入等逻辑沉淀到公共模块；
5. 让 `scripts/` 只保留 CLI glue，不再承载核心算法逻辑；
6. 保持现有可运行脚本和测试在迁移过程中可验证，避免一次性大改导致行为不可追踪。

## 3. 非目标

本次重构不解决以下问题：

- 不新增 `punchline_candidates`、`button_worthy_intensity` 等算法能力；
- 不重新设计 prompt 内容；
- 不改变现有输出 JSON 的业务含义；
- 不引入统一 pipeline 框架基类；
- 不接入新的模型 provider；
- 不调整前端播放器或后端 API。

这些能力应在目录重构完成并通过回归验证后再单独开发。

## 4. 目标目录结构

重构后的 `pipelines/` 结构建议如下：

```text
pipelines/
  client/
    __init__.py
    common.py
    openai_client.py
    volc_ark.py
    factory.py

  common/
    __init__.py
    time.py
    subtitles.py
    media.py
    sampling.py
    dataset.py
    artifacts.py

  expression_trigger/
    __init__.py
    labels.py
    types.py
    parsing.py
    prompts.py
    baseline_mllm.py
    baseline_text.py
    workflow.py
    candidates.py
    review.py
    postprocess.py
    resonance.py

  story_chapter/
    __init__.py
    types.py
    parsing.py
    prompts.py
    baseline_text.py
    baseline_mllm.py

  inner_voice_danmaku/
    __init__.py
    types.py
    parsing.py
    prompts.py
    pipeline.py
```

### 4.1 `pipelines/client`

`client` 是外部模型供应商适配层，单独保留，不并入 `common`。

职责：

- 定义 LLM client protocol；
- 封装 Ark / OpenAI 多模态 JSON 调用；
- 处理 JSON 提取和修复；
- 提供统一的 env 配置读取与 client 构建入口。

新增建议：

- `pipelines/client/factory.py`
  - 从 `.env` 或环境变量读取 `LLM_PROVIDER`、`API_KEY`、`BASE_URL`、`MODEL`；
  - 保留对 `ARK_API_KEY`、`OPENAI_API_KEY` 等历史变量的兼容；
  - 替代当前脚本里的 `build_llm_client`。

### 4.2 `pipelines/common`

`common` 只放无业务归属的基础能力。

职责：

- `time.py`：时间四舍五入、时间窗口规范化；
- `subtitles.py`：SRT 解析、字幕加载、字幕 timeline 格式化；
- `media.py`：视频时长探测、按时间戳抽帧；
- `sampling.py`：均匀采样、窗口内采样、去重采样；
- `dataset.py`：DataForAlgorithm 数据集发现、episode 输入对象；
- `artifacts.py`：通用 JSON artifact 写入、失败诊断写入。

`common` 不应依赖具体算法包。

### 4.3 `pipelines/expression_trigger`

`expression_trigger` 是当前最重要的算法线，纳入主链路和两个 baseline。

职责拆分：

- `labels.py`
  - 四按钮标签定义；
  - legacy alias；
  - 类型归一化；
  - hard negative 规则使用的基础标签说明。
- `types.py`
  - `ExpressionTrigger`；
  - `ExpressionCandidate`；
  - `CandidateDecision`；
  - `WorkflowExpressionTriggerResult`；
  - `ResonanceCue`。
- `parsing.py`
  - LLM 输出解析；
  - trigger / candidate / decision 结构校验；
  - highlight asset 兼容转换。
- `prompts.py`
  - system prompt；
  - baseline prompt；
  - workflow candidate prompt；
  - workflow review prompt。
- `baseline_mllm.py`
  - 当前 `expression_trigger_detection.py` 中的纯 MLLM baseline。
- `baseline_text.py`
  - 当前 `text_expression_trigger_detection.py` 中的纯文本 LLM baseline。
- `workflow.py`
  - 当前 `workflow_expression_trigger_detection.py` 的主编排类；
  - 负责串联候选召回、候选复核、后处理和 resonance cue 生成。
- `candidates.py`
  - 视觉候选窗口；
  - 候选阶段 frame 采样；
  - 候选生成 prompt 调用结果解析入口。
- `review.py`
  - review 阶段 frame 采样；
  - candidate decision 解析；
  - 复核 prompt 调用结果处理。
- `postprocess.py`
  - 强度 / 置信度阈值；
  - 同类相邻触发点合并；
  - 数量控制；
  - 排序。
- `resonance.py`
  - 前端 resonance cue 映射；
  - 四按钮 icon、label、feedback text；
  - base count 估算。

### 4.4 `pipelines/story_chapter`

`story_chapter` 保留两个 baseline：

- `baseline_text.py`：当前 `story_chapter_generation.py`；
- `baseline_mllm.py`：当前 `story_chapter_generation_multimodal.py`。

拆分重点是让 prompt、解析和 pipeline 编排分开，但不做复杂框架化。

### 4.5 `pipelines/inner_voice_danmaku`

`inner_voice_danmaku` 保留当前心里话弹幕算法。

建议拆分：

- `types.py`：输入窗口、弹幕项、输出 cue 类型；
- `prompts.py`：语义生成 prompt；
- `parsing.py`：LLM 输出解析和 fallback 校验；
- `pipeline.py`：主编排流程。

## 5. `scripts/` 目标边界

重构后，`scripts/` 只承担以下职责：

1. 解析 CLI 参数；
2. 调用 `pipelines.client.factory` 创建模型 client；
3. 调用对应 pipeline；
4. 打印进度；
5. 将 pipeline 输出交给 artifact writer。

脚本中不再保存以下逻辑：

- 数据集目录扫描；
- episode 输入对象定义；
- LLM provider 选择；
- trigger 到 highlight asset 的转换；
- 通用失败诊断；
- 核心输出 JSON schema 拼装。

建议保留的算法运行脚本：

```text
scripts/run_expression_trigger_workflow_batch.py
scripts/run_expression_trigger_mllm_baseline_batch.py
scripts/run_expression_trigger_text_baseline_batch.py
scripts/run_story_chapter_text.py
scripts/run_story_chapter_text_batch.py
scripts/run_story_chapter_mllm.py
scripts/run_story_chapter_mllm_batch.py
scripts/run_inner_voice_danmaku.py
```

旧脚本可在迁移期通过薄 wrapper 保留一轮，例如：

```text
scripts/run_workflow_expression_trigger_detection_batch.py
```

该 wrapper 只 import 新脚本入口并调用，不再包含业务逻辑。确认 README、文档和测试全部迁移后，再删除 wrapper。

## 6. 删除清单

以下文件属于旧 highlight / interaction plan 实现，应在迁移中删除：

```text
pipelines/highlight_candidate_generation.py
pipelines/highlight_recognition.py
pipelines/interaction_plan_generation.py
pipelines/old_version/highlight_candidate_generation.py
pipelines/old_version/highlight_recognition.py
pipelines/old_version/interaction_plan_generation.py
```

对应脚本应删除或替换为明确不可用说明：

```text
scripts/run_highlight_candidate_generation.py
scripts/run_highlight_recognition.py
scripts/run_interaction_plan_generation.py
```

对应测试应同步删除或改写：

```text
tests/test_highlight_candidate_generation.py
tests/test_highlight_candidate_generation_script.py
tests/test_highlight_recognition.py
tests/test_highlight_recognition_script.py
tests/test_interaction_plan_generation.py
tests/test_interaction_plan_generation_script.py
```

相关 README 和开发文档中旧链路说明需要同步更新，避免评审或协作者继续使用旧入口。

## 7. 迁移映射

建议迁移关系如下：

```text
pipelines/workflow_expression_trigger_detection.py
  -> pipelines/expression_trigger/workflow.py
  -> pipelines/expression_trigger/candidates.py
  -> pipelines/expression_trigger/review.py
  -> pipelines/expression_trigger/postprocess.py
  -> pipelines/expression_trigger/resonance.py
  -> pipelines/expression_trigger/prompts.py

pipelines/expression_trigger_detection.py
  -> pipelines/expression_trigger/baseline_mllm.py
  -> pipelines/expression_trigger/labels.py
  -> pipelines/expression_trigger/parsing.py

pipelines/text_expression_trigger_detection.py
  -> pipelines/expression_trigger/baseline_text.py

pipelines/story_chapter_generation.py
  -> pipelines/story_chapter/baseline_text.py
  -> pipelines/story_chapter/prompts.py
  -> pipelines/story_chapter/parsing.py

pipelines/story_chapter_generation_multimodal.py
  -> pipelines/story_chapter/baseline_mllm.py

pipelines/inner_voice_danmaku_generation.py
  -> pipelines/inner_voice_danmaku/pipeline.py
  -> pipelines/inner_voice_danmaku/prompts.py
  -> pipelines/inner_voice_danmaku/parsing.py

pipelines/utils.py
  -> pipelines/common/subtitles.py
  -> pipelines/common/media.py
  -> pipelines/common/sampling.py
  -> pipelines/common/time.py

scripts/run_expression_trigger_detection_batch.py
  -> pipelines/common/dataset.py
  -> pipelines/common/artifacts.py
  -> pipelines/client/factory.py
  -> scripts/run_expression_trigger_mllm_baseline_batch.py

scripts/run_workflow_expression_trigger_detection_batch.py
  -> scripts/run_expression_trigger_workflow_batch.py
```

## 8. 兼容策略

为降低一次性迁移风险，建议采用两阶段兼容：

### 8.1 第一阶段：新结构落地，旧入口保留 shim

旧 import 路径保留薄文件，例如：

```python
from pipelines.expression_trigger.workflow import WorkflowExpressionTriggerPipeline
```

这样现有测试可以逐步迁移，而不是一次性全部改完。

保留 shim 的对象：

- `pipelines/workflow_expression_trigger_detection.py`
- `pipelines/expression_trigger_detection.py`
- `pipelines/text_expression_trigger_detection.py`
- `pipelines/story_chapter_generation.py`
- `pipelines/story_chapter_generation_multimodal.py`
- `pipelines/inner_voice_danmaku_generation.py`

不保留 shim 的对象：

- 旧 highlight / interaction plan 文件。

### 8.2 第二阶段：测试和文档全部迁移到新路径

确认新路径测试稳定后，删除上述 shim，避免长期双路径维护。

## 9. 测试策略

重构必须以“行为不变”为第一原则。

建议测试分三层：

1. 公共模块测试：
   - subtitle parse；
   - frame timestamp sampling；
   - visual window sampling；
   - dataset discovery；
   - artifact writer。
2. 算法模块测试：
   - expression trigger parsing；
   - candidate parsing；
   - candidate decision parsing；
   - postprocess 合并；
   - resonance cue 映射；
   - story chapter parsing；
   - inner voice danmaku parsing。
3. 脚本 smoke 测试：
   - batch 参数解析；
   - fake pipeline 输出写入；
   - skip / force / failure diagnostics；
   - wrapper 兼容入口。

重构每一步完成后至少运行：

```bash
python -m pytest tests/test_workflow_expression_trigger_detection.py -q
python -m pytest tests/test_workflow_expression_trigger_detection_batch_script.py -q
python -m pytest tests/test_text_expression_trigger_detection.py -q
python -m pytest tests/test_text_expression_trigger_detection_batch_script.py -q
python -m pytest tests/test_story_chapter_generation.py -q
python -m pytest tests/test_story_chapter_generation_multimodal.py -q
python -m pytest tests/test_inner_voice_danmaku_generation.py -q
```

最后运行全量测试：

```bash
python -m pytest -q
```

## 10. 文档更新策略

需要同步更新：

- `README.md` 中算法链路说明；
- `docs/develop-docs/status/current-implementation.md`；
- `docs/develop-docs/status/algorithm-validation-current-status.md`；
- 与旧 highlight / interaction plan 相关的模块设计说明。

文档中应明确：

- 当前保留的三条算法线；
- expression trigger 主链路和两个 baseline 的关系；
- story chapter 两个 baseline 的关系；
- inner voice danmaku 的定位；
- 旧 highlight / interaction plan 已废弃。

## 11. 推荐实施顺序

建议按以下顺序实施：

1. 新建 `pipelines/common` 和 `pipelines/client/factory.py`；
2. 迁移公共 subtitle / media / sampling 工具，并保留 `pipelines/utils.py` shim；
3. 新建 `pipelines/expression_trigger`，先迁移 labels、types、parsing；
4. 迁移 expression trigger 三个 pipeline：workflow、MLLM baseline、text baseline；
5. 迁移 workflow batch 脚本为薄 CLI；
6. 迁移 story chapter 包；
7. 迁移 inner voice danmaku 包；
8. 删除旧 highlight / interaction plan 文件、脚本和测试；
9. 更新 README 和开发状态文档；
10. 全量测试和一次本地评估 smoke check。

## 12. 设计取舍

本设计选择“产品线分包 + 有限拆模块”，而不是彻底框架化。

原因：

- 当前最重要的目标仍然是算法验证和比赛展示，不是建设通用 pipeline framework；
- 三条算法线的输入输出和中间过程不同，过早抽象统一基类会增加理解成本；
- expression trigger 下一步要快速迭代候选召回和 review 策略，先把它拆成清晰模块收益最高；
- story chapter 和 inner voice danmaku 当前可以先迁入独立包，后续按真实复杂度再继续拆。

## 13. 验收标准

本次重构完成后，应满足：

1. `pipelines/` 下只保留三条确定算法线、`client` 和 `common`；
2. 旧 highlight / interaction plan 实现已删除；
3. `scripts/` 中算法运行入口都是薄 CLI；
4. expression trigger workflow 的候选生成、候选复核、后处理、resonance cue 逻辑分别位于独立模块；
5. 现有算法输出结构保持兼容；
6. README 和状态文档不再指向旧算法链路；
7. 相关单测和全量测试通过。

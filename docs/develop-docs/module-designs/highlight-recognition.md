# 高光点识别模块设计

> 本文档记录早期高光识别设计。当前算法主线已迁移为 Expression Trigger，代码入口为 `pipelines/expression_trigger/`。旧 `highlight_recognition` pipeline 已废弃并移除。

## 1. 模块定位

高光点识别模块负责从短剧视频和字幕中识别适合触发互动的剧情片段，并输出结构化的 `Highlight Asset` 列表。

在系统链路中，它位于原始视频/字幕数据之后、交互方案生成模块之前：

```text
video_file_path + subtitle_file_path
  ↓
高光点识别模块
  ↓
Highlight Asset
  ↓
交互方案生成模块
```

本模块不负责前端渲染，也不负责用户反馈策略更新。它只解决一个问题：`哪里值得互动`。

MVP 阶段采用“字幕 + 多图理解 + 结构化校验”的方式完成最简实现。

## 2. 设计目标

第一版实现优先满足以下目标：

1. 从视频和字幕中识别 1 个或多个高光片段；
2. 输出符合 `packages/contracts/schemas/highlight-asset.schema.json`；
3. 结果尽量可解释、可回退，适合比赛答辩；
4. 不依赖复杂训练流程、标注模型或用户画像；
5. 能与后续交互方案生成模块无缝衔接。

## 3. 输入

### 3.1 必需输入

#### `video_id`

视频唯一标识，用于串联后续的 `Interaction Plan`、样例输出和本地数据目录。

#### `video_file_path`

短剧视频文件路径。

模块会根据视频时长和字幕时长共同决定抽帧范围。

#### `subtitle_file_path`

字幕文件路径，优先作为剧情语义上下文。

当前实现支持标准 SRT，也兼容简化文本。

### 3.2 内部派生输入

#### 抽帧时间戳

模块会根据视频或字幕时长生成采样时间戳。

支持一类采样参数：

- `sample_interval_sec`：采样间隔，表示每隔多少秒取一帧，例如 1s 1 帧、2s 1 帧。

如果采样帧数超过 `max_frames`，模块不再从前往后截断，而是使用 `max_frames` 在完整时间线上重新均匀采样。采样序列包含 0 秒。

#### 视频帧

从视频中按时间戳抽帧，作为多图理解输入。

#### 字幕时间线

字幕会被整理成固定格式字符串，作为大模型的文本上下文。

## 4. 输出

模块输出 `Highlight Asset` 列表。

每个对象必须符合 `highlight-asset.schema.json`，核心字段包括：

- `highlight_id`
- `video_id`
- `start_time`
- `end_time`
- `highlight_type`
- `emotion`
- `intensity`
- `summary`
- `reason`
- `confidence`

示例：

```json
{
  "highlight_id": "h_case1_ep01_001",
  "video_id": "case1_ep01",
  "start_time": 38.0,
  "end_time": 46.0,
  "highlight_type": "身份揭露",
  "emotion": "震惊",
  "intensity": 0.92,
  "summary": "男主真实身份曝光，反派震惊。",
  "reason": "前文一直铺垫男主被轻视，此处身份反转带来强爽点。",
  "confidence": 0.88,
  "highlight_score": 0.86,
  "status": "verified"
}
```

## 5. 处理流程

### 5.1 时长估计

模块先读取字幕时长和视频时长，取更长者作为采样边界。

### 5.2 时间戳采样

根据 `sample_interval_sec` 生成时间戳序列；如果超过 `max_frames`，则按完整时间线均匀重采样。

### 5.3 多图理解输入构造

模块将以下内容组织为大模型输入：

- 系统提示词；
- 统一格式的字幕时间线；
- 带时间戳标记的图片序列；
- 采样时间戳说明。

图片输入采用多图理解形式，而不是单独的视频 URL。

### 5.4 结构化输出校验

大模型输出后，模块只保留满足约束的结果：

- `start_time` 和 `end_time` 是合法数值；
- `end_time > start_time`；
- `intensity` 和 `confidence` 必须在 `0~1` 之间；
- `highlight_type`、`emotion`、`summary`、`reason` 不能为空。

不合法的条目会被丢弃。

## 6. Prompt 约束

为减少不可靠输出，prompt 中需要明确字段要求：

- `start_time` / `end_time` 使用秒；
- `highlight_type` 只写短标签；
- `emotion` 只写主情绪标签；
- `intensity` 必须是 `0~1`；
- `confidence` 必须是 `0~1`；
- `summary` 和 `reason` 必须严格依赖字幕和画面；
- 没有证据时宁可少报，也不要硬编。

## 7. 模块边界

### 7.1 本模块负责

1. 读取视频和字幕；
2. 抽帧；
3. 组织多模态 prompt；
4. 调用火山方舟模型；
5. 解析和校验输出；
6. 产出 `Highlight Asset`。

### 7.2 本模块不负责

1. 不生成互动方案；
2. 不渲染前端 UI；
3. 不记录用户事件；
4. 不做策略更新；
5. 不做复杂训练或分类器推理。

## 8. 实现接口

早期脚本入口已废弃：

```text
scripts/run_highlight_recognition.py
```

当前 Expression Trigger 主链路入口：

```bash
python scripts/expression_trigger/run_workflow_batch.py --video-id case1_ep01 --force
```

输出写入：

```text
output/<video_id>/expression_triggers.json
output/<video_id>/expression_triggers.debug.json
```

`ARK_BASE_URL`、`ARK_API_KEY`、`ARK_MODEL` 从 `.env` 读取，也可由进程环境变量覆盖。

## 9. 与后续模块的关系

高光点识别模块只负责输出 `Highlight Asset`，不关心后续如何生成互动方案。

交互方案生成模块只消费 `Highlight Asset`，不修改它。

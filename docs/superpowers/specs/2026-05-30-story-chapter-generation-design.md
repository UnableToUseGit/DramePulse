# Story Chapter 生成 Pipeline 设计记录

## 1. 背景

`Story Navigation` 时间轴增强需要一份可被前端消费的剧情章节数据。前端只负责把章节节点展示在播放器进度条上，不负责理解剧情结构，也不负责判断章节边界。

因此需要在 `pipelines/` 下新增 `Story Chapter` 生成能力：

```text
transcription.json + scene_detection.json
  -> 字幕结构化抽取
  -> 剧情章节草稿
  -> 镜头边界吸附
  -> story_chapters.json
```

第一版目标是为剧情导航提供稳定数据基础，不处理前端 UI，也不把章节节点混同为即时互动触发点。

## 2. 输入范围

第一版只支持现有转写 JSON，不支持 `.srt`。

命令输入：

```text
--transcription output/{video_id}/video.transcription.json
--scene-detection output/{video_id}/scene_detection.json
```

`transcription.json` 沿用现有阿里云转写结果结构，由 pipeline 解析为 `Utterance` 列表。该解析逻辑可以参考 `pipelines/old_version/highlight_candidate_generation.py` 中的 `load_utterances_from_transcription`。

`scene_detection.json` 沿用 `scripts/run_scene_detection.py` 输出结构，由 pipeline 读取 `scenes` 数组，用于章节边界吸附。

## 3. 输出契约

输出路径：

```text
output/{video_id}/story_chapters.json
```

顶层结构：

```json
{
  "video_id": "demo_ep01",
  "created_at": "2026-05-30T00:00:00Z",
  "source": {
    "transcription_path": "output/demo_ep01/video.transcription.json",
    "scene_detection_path": "output/demo_ep01/scene_detection.json"
  },
  "story_chapters": [
    {
      "chapter_id": "ch_demo_ep01_001",
      "video_id": "demo_ep01",
      "start_time": 0.0,
      "end_time": 18.4,
      "title": "开局设定",
      "summary": "女主醒来发现处境异常，故事冲突开始铺垫。",
      "chapter_type": "setup",
      "importance": 0.62
    }
  ],
  "warnings": []
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `chapter_id` | 章节 ID，由 pipeline 按输出顺序生成 |
| `video_id` | 视频 ID |
| `start_time` | 吸附到镜头边界后的章节开始时间，秒 |
| `end_time` | 吸附到镜头边界后的章节结束时间，秒 |
| `title` | 时间轴展示用短标题 |
| `summary` | 章节摘要，用于调试和后续展示 |
| `chapter_type` | 章节类型，例如 `setup`、`conflict`、`reversal`、`climax`、`ending` |
| `importance` | 重要度，0 到 1 |

## 4. 处理流程

### 4.1 字幕解析

pipeline 读取 `transcription.json`，提取按时间递增的 `Utterance`：

```json
{
  "utterance_id": "u_001",
  "start_time": 1.0,
  "end_time": 2.5,
  "text": "你卖的是假的。",
  "speaker_id": "2"
}
```

空文本、非法时间和结束时间不大于开始时间的句子会被忽略。

### 4.2 LLM 结构化抽取

LLM 只基于字幕时间线抽取剧情章节草稿。

要求：

- 章节是连续剧情段落，不是单句高光点；
- 不判断“是否适合互动”；
- 不输出弹幕、投票或表达触发信息；
- 不强制章节数量；
- 标题要短，适合显示在进度条附近；
- 摘要和类型必须由字幕内容支撑。

LLM 返回形态：

```json
{
  "chapters": [
    {
      "start_time": 0.0,
      "end_time": 18.4,
      "title": "开局设定",
      "summary": "女主醒来发现处境异常，故事冲突开始铺垫。",
      "chapter_type": "setup",
      "importance": 0.62
    }
  ]
}
```

### 4.3 镜头边界吸附

LLM 输出的 `start_time` 和 `end_time` 只是剧情语义边界，可能切断镜头。pipeline 必须用 `scene_detection.json` 做确定性吸附。

吸附规则：

- `start_time` 吸附到覆盖该时间点的 scene 的 `start_time`；
- `end_time` 吸附到覆盖该时间点的 scene 的 `end_time`；
- 如果时间点落在所有 scene 外，吸附到最近 scene 边界；
- 如果吸附后 `end_time <= start_time`，丢弃该章节，并向 `warnings` 写入原因；
- 不强行补齐整集；
- 不强行控制章节数量；
- 不做复杂合并、拆分或个性化排序。

吸附后的章节按 `start_time` 升序输出。

### 4.4 合法性校验

丢弃以下章节：

- 缺少 `start_time` 或 `end_time`；
- `end_time <= start_time`；
- `title` 为空；
- `summary` 为空；
- `importance` 不在 0 到 1；
- 吸附后时间区间非法。

保留 `chapter_type` 的原始短标签；如果为空，使用 `unknown`。

## 5. 模块边界

建议新增文件：

```text
pipelines/story_chapter_generation.py
scripts/run_story_chapter_generation.py
tests/test_story_chapter_generation.py
tests/test_story_chapter_generation_script.py
```

`pipelines/story_chapter_generation.py` 负责：

- 读取转写 JSON；
- 读取 scene detection JSON；
- 构建 LLM prompt；
- 解析 LLM 返回；
- 执行镜头边界吸附；
- 写出 `story_chapters.json`。

`scripts/run_story_chapter_generation.py` 负责：

- 解析命令行参数；
- 构造 Ark LLM client；
- 调用 pipeline；
- 打印输出路径。

不修改旧版 `highlight_candidate_generation`，只参考其结构和测试风格。

## 6. 错误处理

- 输入文件不存在时直接抛出 `FileNotFoundError`；
- 转写 JSON 无可用字幕时输出空 `story_chapters`，并记录 warning；
- scene 文件无可用镜头时不做吸附，使用 LLM 原始时间，并记录 warning；
- LLM 返回非法 JSON shape 时输出空 `story_chapters`，并记录 warning；
- 单个章节非法时丢弃该章节，不影响其他章节输出。

## 7. 测试要求

单元测试覆盖：

1. 从阿里云转写 JSON 解析 `Utterance`；
2. 解析合法 LLM 章节草稿；
3. 丢弃非法章节；
4. `start_time/end_time` 吸附到覆盖 scene 的起止边界；
5. 时间点落在 scene 外时吸附到最近边界；
6. pipeline 写出 `story_chapters.json`；
7. CLI 将参数正确传递给 pipeline。

验证命令：

```bash
pytest tests/test_story_chapter_generation.py tests/test_story_chapter_generation_script.py
```

如改动影响共享解析逻辑，还需运行：

```bash
pytest tests/test_highlight_candidate_generation.py tests/test_scene_detection_script.py
```

## 8. 非目标

第一版不做：

- `.srt` 输入支持；
- 章节数量控制；
- 强行生成 3 到 6 个章节；
- 前端 UI；
- 后端 API；
- 剧情搜索；
- 自动跳过铺垫；
- 个性化导航；
- 将章节节点转成互动触发点。

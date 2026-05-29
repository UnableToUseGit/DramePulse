# 视频 Manifest 设计

## 1. 背景

第一阶段的数据工作目标是把人工整理的短剧视频、抖音元信息和弹幕数据稳定入库，供前端调试、算法处理和标注工具共同使用。

当前外部数据目录约定为：

```text
VideoData/
  raw/
    <series_id>/
      epXX/
        video.mp4
        douyin.json
  video_manifest.json
```

其中：

- `video.mp4` 来自番茄达人中心手动下载；
- `douyin.json` 来自 `scripts/douyin_danmaku_collector.py`，包含抖音视频元信息和弹幕；
- `video_manifest.json` 是数据集索引，供后续入库脚本消费。

`scripts/douyin_targets.csv` 是采集任务输入，不属于 `VideoData` 交付物。

## 2. 设计目标

`video_manifest.json` 负责回答：

1. 这个数据集中有哪些视频；
2. 每个视频对应哪部剧、哪一集；
3. 视频文件和抖音 JSON 文件在哪里；
4. 哪些字段可以直接写入 `videos` 表；
5. 前端、后端、算法和标注工具如何使用同一个 `video_id`。

第一版 manifest 只覆盖视频入库和基础调试，不包含高光点、互动方案或人工标注结果。

## 3. 文件位置

默认生成位置：

```text
<data-root>/video_manifest.json
```

示例：

```text
/Users/qinminghao/Desktop/ByteDance/VideoData/video_manifest.json
```

manifest 内部不保存 `dataset_root` 或本机绝对路径。所有路径都相对运行脚本时传入的 `--data-root` 解析。

示例生成命令：

```bash
python scripts/generate_video_manifest.py \
  --data-root /Users/qinminghao/Desktop/ByteDance/VideoData
```

示例入库命令：

```bash
python services/api/scripts/import_video_manifest.py \
  --manifest /Users/qinminghao/Desktop/ByteDance/VideoData/video_manifest.json \
  --data-root /Users/qinminghao/Desktop/ByteDance/VideoData
```

## 4. Manifest 结构

```json
{
  "schema_version": "video_manifest.v1",
  "generated_at": "2026-05-24T18:00:00+08:00",
  "videos": [
    {
      "video_id": "beipai_xunbao_biji_ep63",
      "series_id": "beipai_xunbao_biji",
      "series_name": "北派寻宝笔记",
      "episode_no": 63,
      "episode_label": "ep63",
      "title": "从 douyin.json metadata.title 提取",
      "duration": 123.45,
      "source": "local",
      "status": "active",
      "storage": {
        "bucket": "local",
        "object_key": "raw/beipai_xunbao_biji/ep63/video.mp4",
        "content_type": "video/mp4",
        "size": 12345678
      },
      "douyin": {
        "video_id": "7622167244545609002",
        "video_url": "https://www.douyin.com/video/7622167244545609002",
        "json_path": "raw/beipai_xunbao_biji/ep63/douyin.json",
        "danmaku_count": 1234,
        "available": true
      }
    }
  ]
}
```

## 5. 字段说明

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | 固定为 `video_manifest.v1`。 |
| `generated_at` | string | 是 | manifest 生成时间，ISO 8601 格式。 |
| `videos` | array | 是 | 视频条目列表。 |
| `video_id` | string | 是 | 系统内稳定视频 ID，格式为 `<series_id>_<episode_label>`。 |
| `series_id` | string | 是 | 剧集稳定标识，用于路径、分组和工程逻辑。 |
| `series_name` | string | 是 | 中文剧名，用于前端展示。 |
| `episode_no` | integer | 是 | 集数。 |
| `episode_label` | string | 是 | 集数标签，例如 `ep01`、`ep63`。 |
| `title` | string | 是 | 单集标题或抖音描述，从 `douyin.json` 中提取。 |
| `duration` | number/null | 是 | 视频时长，单位秒；无法提取时为 `null`。 |
| `source` | string | 是 | 第一阶段固定为 `local`。 |
| `status` | string | 是 | 第一阶段固定为 `active`。 |
| `storage.bucket` | string | 是 | 本地模式默认 `local`。 |
| `storage.object_key` | string | 是 | 视频文件相对 `--data-root` 的路径。 |
| `storage.content_type` | string | 是 | 第一阶段固定为 `video/mp4`。 |
| `storage.size` | integer | 是 | 视频文件大小，单位字节。 |
| `douyin.video_id` | string/null | 是 | 抖音视频 ID；缺少 `douyin.json` 时为 `null`。 |
| `douyin.video_url` | string/null | 是 | 抖音网页地址；缺少 `douyin.json` 时为 `null`。 |
| `douyin.json_path` | string/null | 是 | 抖音 JSON 相对 `--data-root` 的路径；缺少 `douyin.json` 时为 `null`。 |
| `douyin.danmaku_count` | integer | 是 | 去重后的弹幕数量；缺少 `douyin.json` 时为 `0`。 |
| `douyin.available` | boolean | 是 | `douyin.json` 是否已存在并成功参与 manifest 生成。 |

## 6. videos 表映射

manifest 入库时写入 `videos` 表。建议 `videos` 表在现有字段基础上增加：

```text
series_id
series_name
episode_label
douyin_video_id
douyin_json_path
```

字段映射：

| videos 表字段 | manifest 字段 |
| --- | --- |
| `video_id` | `video_id` |
| `series_id` | `series_id` |
| `series_name` | `series_name` |
| `episode_no` | `episode_no` |
| `episode_label` | `episode_label` |
| `title` | `title` |
| `duration` | `duration` |
| `oss_bucket` | `storage.bucket` |
| `oss_object_key` | `storage.object_key` |
| `content_type` | `storage.content_type` |
| `size` | `storage.size` |
| `source` | `source` |
| `status` | `status` |
| `douyin_video_id` | `douyin.video_id` |
| `douyin_json_path` | `douyin.json_path` |

`douyin.danmaku_count` 第一版不写入 `videos` 表，只用于 manifest 校验和人工检查。

## 7. 生成规则

`scripts/generate_video_manifest.py` 后续应按以下规则生成 manifest：

1. 扫描 `<data-root>/raw/<series_id>/epXX/`；
2. 每个 episode 目录必须存在 `video.mp4`；
3. `video_id` 使用 `<series_id>_<episode_label>`；
4. `series_name` 从采集脚本的剧名映射或同源配置中取得；
5. 如果存在 `douyin.json`，`title` 从 `douyin.json.metadata.title` 提取；
6. 如果缺少 `douyin.json`，`title` 使用 `<series_name> <episode_label>`；
7. 如果存在 `douyin.json`，`duration` 从 `douyin.json.metadata.duration_ms` 转换为秒；
8. 如果缺少 `douyin.json`，`duration` 为 `null`；
9. 如果存在 `douyin.json`，`douyin.video_id` 使用 `douyin.json.video_id`；
10. 如果存在 `douyin.json`，`douyin.video_url` 使用 `douyin.json.video_url`；
11. 如果存在 `douyin.json`，`douyin.danmaku_count` 使用 `douyin.json.danmaku.count`；
12. 如果缺少 `douyin.json`，`douyin.video_id`、`douyin.video_url` 和 `douyin.json_path` 为 `null`，`douyin.danmaku_count` 为 `0`，`douyin.available` 为 `false`；
13. 如果存在 `douyin.json`，`douyin.available` 为 `true`；
14. `storage.size` 使用本地 `video.mp4` 文件大小。

如果缺少 `video.mp4`，生成脚本应失败并报告具体 episode。缺少 `douyin.json` 不阻断 manifest 生成，相关字段使用上面的默认值。

## 8. 使用边界

manifest 是数据集索引，不是业务结果。

第一版不在 manifest 中保存：

- 高光点识别结果；
- 互动方案；
- 用户行为事件；
- 人工标注结果；
- 字幕文件路径。

字幕是算法中间产物，后续如果需要统一管理，可以新增 `derived` 或独立 manifest，不混入视频入库 manifest。

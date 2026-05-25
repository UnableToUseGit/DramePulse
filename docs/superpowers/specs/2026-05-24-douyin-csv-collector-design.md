# Douyin CSV Collector Design

## Goal

把 DramePulse 仓库内的 `scripts/douyin_danmaku_collector.py` 改成支持 CSV 批量输入，用于把人工整理的抖音视频 ID 采集成和 `VideoData` 原始数据目录对齐的 `douyin.json`。

## Input

新增 CSV 输入，支持带表头和不带表头两种格式。当前第一批目标放在 `scripts/douyin_targets.csv`，不要放进外部 `VideoData` 目录。

带表头格式：

```csv
series_name,episode_no,douyin_video_id
北派寻宝笔记,63,7546166458309430554
```

无表头格式：

```csv
北派寻宝笔记,63,7546166458309430554
```

字段含义：

- `series_name`：人工填写的中文剧名。
- `episode_no`：集数，可写 `63`、`ep63` 或 `第63集`。
- `douyin_video_id`：抖音网页视频 ID，允许带 `douyin_` 前缀，最终会归一化为纯数字。

## Output

`--output-dir` 指向外部数据根目录，例如：

```text
/Users/qinminghao/Desktop/ByteDance/VideoData
```

每条 CSV 记录写入：

```text
<output-dir>/raw/<series_id>/epXX/douyin.json
```

其中 `series_id` 由内置中文剧名映射得到，`epXX` 由集数归一化得到。

## Series Mapping

第一版内置当前已整理的 10 部剧映射：

```text
云渺1 -> yunmiao_1
北往 -> beiwang
北派寻宝笔记 -> beipai_xunbao_biji
十八岁太奶奶 -> shibasui_tainainai
天下第一纨绔 -> tianxia_diyi_wanku
家里家外 -> jiali_jiawai
幸得相遇离婚时 -> xingde_xiangyu_lihunshi
撕夜 -> siye
荒年全村啃树皮 -> huangnian_quancun_kenshupi
那年冬至 -> nanian_dongzhi
```

如果 CSV 中出现未配置剧名，脚本直接报错，避免采集结果落到错误目录。

## Compatibility

保留原有 JSON manifest 模式。新增模式使用 `--csv` 和 `--output-dir`；未传 `--csv` 时，仍按原来的 `--manifest` 和 `--out-dir` 行为运行。

推荐运行方式：

```bash
python scripts/douyin_danmaku_collector.py \
  --csv scripts/douyin_targets.csv \
  --output-dir /Users/qinminghao/Desktop/ByteDance/VideoData \
  --headed
```

## Validation

本次只验证 CSV 解析、剧名映射、集数归一化和输出路径生成，不运行真实抖音采集。

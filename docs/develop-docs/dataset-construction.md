# 数据集构建说明

## 1. 原始数据收集

来源平台：抖音

候选短剧列表：

| 剧集名称 | 类型 | 集数 | 本集标题 | 链接 |
| --- | --- | --- | --- | --- |
| 八零辣妻，揣着四宝撩夫 | 爱情 | 第一集 | 穿越的我一睁开眼，竟然在别人床上 | https://www.douyin.com/video/7632154313724267830 |
| 八零辣妻，揣着四宝撩夫 | 爱情 | 第二集 | 女主拒绝逼婚，无奈被剧情控制 | https://www.douyin.com/video/7630441633112165672 |
| 八零辣妻，揣着四宝撩夫 | 爱情 | 第三集 | 失足坠落房顶，她却意外重生 | https://www.douyin.com/video/7630441647964196096 |
| 谁也别想动我的库里南 | 职场 | 第一集 | 私车公用两年，新来的实习生居然当众举报我公车私用？！ | https://www.douyin.com/video/7618149763493547283 |
| 谁也别想动我的库里南 | 职场 | 第二集 | 真是令人心寒啊，善良在利益面前一文不值！ | https://www.douyin.com/video/7618150072617946404 |
| 谁也别想动我的库里南 | 职场 | 第三集 | 是你的就是你的，不是你的抢了也不会有好结果！ | https://www.douyin.com/video/7618150127756201252 |
| 修仙满级回来后，我儿孙满堂了 | 奇幻 | 第一集 | 误入修仙界修炼百年，竟然因为渡劫又回来了… | https://www.douyin.com/video/7634131980325571850 |
| 修仙满级回来后，我儿孙满堂了 | 奇幻 | 第二集 | 这么年轻的姑娘是我婆婆？ | https://www.douyin.com/video/7634132011061382450 |
| 修仙满级回来后，我儿孙满堂了 | 奇幻 | 第三集 | 妈，你怎么还是四十年前的样子？ | https://www.douyin.com/video/7634132034171997491 |
| 穿书富家妯娌，我和闺蜜齐上阵 | 喜剧 | 第一集 |  | https://www.douyin.com/video/7560185678554729754 |
| 穿书富家妯娌，我和闺蜜齐上阵 | 喜剧 | 第二集 |  | https://www.douyin.com/video/7560185716865600814 |
| 穿书富家妯娌，我和闺蜜齐上阵 | 喜剧 | 第三集 |  | https://www.douyin.com/video/7560185752596925746 |

## 2. 下载方法

### 2.1 视频下载

视频下载工具：https://github.com/CharlesPikachu/videodl#

### 2.2 弹幕爬取

操作步骤：

1. 进入某集短剧页面，按 F12 打开开发者工具，进入“网络”面板。
2. 在“网络”面板的过滤功能中输入 `get_v2`，筛选出 `get_v2` 开头的请求。这是发给后台弹幕接口的请求。
3. 右键该请求，复制完整网址。
4. 将完整网址替换到下面代码中的 `RAW_DANMAKU_URL`。
5. 将代码粘贴到 Console 面板，按回车运行。

```javascript
(async function () {
  // 1. 把 Network 里复制出来的 get_v2 完整 URL 粘到这里
  const RAW_DANMAKU_URL = `在这里粘贴 get_v2 完整 URL`;

  // 2. 默认按抖音真实请求的 32 秒窗口拉取
  const STEP_MS = 32000;

  // 3. 每次请求间隔，别太快
  const INTERVAL_MS = 500;

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function getVideoIdFromUrl() {
    const m = location.href.match(/\/video\/(\d+)/);
    return m ? m[1] : "unknown_video";
  }

  function normalizeDanmaku(x) {
    return {
      danmaku_id: x.danmaku_id,
      item_id: x.item_id,
      user_id: x.user_id,
      time_ms: x.offset_time,
      time_sec: x.offset_time / 1000,
      text: x.text,
      digg_count: x.digg_count,
      score: x.score,
      has_emoji: x.has_emoji,
      danmaku_type: x.danmaku_type,
      is_ad: x.is_ad,
      raw: x
    };
  }

  function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json;charset=utf-8"
    });

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 1000);
  }

  async function fetchJSON(url) {
    const res = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: {
        accept: "application/json, text/plain, */*",
        "x-secsdk-csrf-token": "DOWNGRADE"
      }
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    return await res.json();
  }

  async function fetchAllDanmaku(rawUrl) {
    if (!rawUrl || rawUrl.includes("在这里粘贴")) {
      throw new Error("你还没有把 get_v2 完整 URL 粘到 RAW_DANMAKU_URL 里。");
    }

    const baseUrl = new URL(rawUrl);

    const duration = Number(baseUrl.searchParams.get("duration"));
    const itemId = baseUrl.searchParams.get("item_id");
    const groupId = baseUrl.searchParams.get("group_id");

    if (!duration || Number.isNaN(duration)) {
      throw new Error("没有从 get_v2 URL 中解析到 duration。请确认你粘贴的是完整 get_v2 请求 URL。");
    }

    console.log("[info] group_id:", groupId);
    console.log("[info] item_id:", itemId);
    console.log("[info] duration_ms:", duration);
    console.log("[info] duration_sec:", duration / 1000);

    const all = [];

    for (let start = 0; start < duration; start += STEP_MS) {
      const end = Math.min(start + STEP_MS, duration);

      const url = new URL(baseUrl.toString());
      url.searchParams.set("start_time", String(start));
      url.searchParams.set("end_time", String(end));

      const data = await fetchJSON(url.toString());
      const list = data.danmaku_list || [];

      console.log(
        `[window] ${start} - ${end}, count=${list.length}, total=${data.total}, status=${data.status_code}`
      );

      all.push(...list);

      await sleep(INTERVAL_MS);
    }

    const dedup = Array.from(
      new Map(all.map(x => [x.danmaku_id, x])).values()
    ).sort((a, b) => (a.offset_time || 0) - (b.offset_time || 0));

    console.log(`[done] raw=${all.length}, dedup=${dedup.length}`);

    return {
      group_id: groupId,
      item_id: itemId,
      duration_ms: duration,
      raw_count: all.length,
      dedup_count: dedup.length,
      danmaku: dedup
    };
  }

  try {
    const videoId = getVideoIdFromUrl();

    const result = await fetchAllDanmaku(RAW_DANMAKU_URL);

    const clean = result.danmaku.map(normalizeDanmaku);

    const payload = {
      source_url: location.href,
      video_id_from_url: videoId,
      group_id: result.group_id,
      item_id: result.item_id,
      duration_ms: result.duration_ms,
      count: clean.length,
      danmaku: clean
    };

    console.log("[result]", payload);

    const filename = `douyin_danmaku_${videoId}.json`;
    downloadJSON(payload, filename);

    console.log(`[saved] ${filename}`);
  } catch (err) {
    console.error("[failed]", err);
  }
})();
```

## 3. 原始数据收集结果

原始视频与弹幕数据已上传至 Hugging Face 数据集：

```text
TheThreeKeyboardeers/ShortDramas
```

后续开发和演示时，应先从该数据集下载数据，再移动或整理到本仓库的 `data/` 目录下。

## 4. 高光点验证集标注

本阶段先用 `case1_ep01` 跑通验证集制作流程，不急于扩展样本规模，也不急于定义完整高光类型体系。

第一版验证集只服务一个目标：为高光点识别算法提供可重复对照的人工标注结果。后续 prompt、抽帧策略或模型选择发生变化时，可以用同一批人工标注判断识别结果是否更接近人工标准。

### 4.1 第一版流程

```text
data/case1/ep01.mp4
data/case1/ep01.srt
data/case1/ep01.json
  ↓
apps/annotation-tool/index.html
  ↓
人工标注高光时间段、emotion、reason
  ↓
导出 <video_id>.annotation.json
```

第一版暂不实现自动评测脚本。标注数据格式会预留给后续评测脚本使用。

### 4.2 标注工具

当前标注工具为本地静态页面：

```text
apps/annotation-tool/index.html
```

建议通过仓库内置本地服务打开。该服务支持 HTTP Range 请求，视频原生进度条拖拽、点击跳转，以及工具中的“跳到开始 / 跳到结束”按钮都依赖该能力。

```bash
python scripts/serve_annotation_tool.py --port 8770
```

然后访问：

```text
http://127.0.0.1:8770/apps/annotation-tool/
```

不要直接使用 `python -m http.server` 启动标注工具。Python 标准库静态服务在当前环境下不会为 MP4 返回 `206 Partial Content`，浏览器会认为视频不可 seek，表现为进度条拖拽或按钮跳转后又回到原播放位置。

工具第一版能力：

- 播放 `data/case1/ep01.mp4`；
- 读取 `data/case1/ep01.json` 中的 `danmaku`；
- 在播放器右侧展示按时间排序的弹幕列表；
- 视频播放时自动滚动到当前时间对应的弹幕行；
- 点击弹幕行可以跳转到对应视频时间；
- 支持记录 `start_time` 和 `end_time`；
- 支持填写 `emotion` 和 `reason`；
- 支持添加、删除标注；
- 支持导出人工标注 JSON。

### 4.3 标注字段

第一版人工标注字段刻意保持精简：

```json
{
  "video_id": "case1_ep01",
  "video_path": "data/case1/ep01.mp4",
  "subtitle_path": "data/case1/ep01.srt",
  "source_json_path": "data/case1/ep01.json",
  "annotations": [
    {
      "annotation_id": "gold_case1_ep01_001",
      "start_time": 8.96,
      "end_time": 12.04,
      "emotion": "shock",
      "reason": "开场女主醒来发现自己正在亲吻陌生男人，弹幕集中吐槽和震惊，适合作为互动触发点。"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `annotation_id` | 人工标注 ID，由导出工具按顺序生成。 |
| `start_time` | 高光开始时间，单位为秒。 |
| `end_time` | 高光结束时间，单位为秒，必须大于 `start_time`。 |
| `emotion` | 该高光主要激发的用户情绪。 |
| `reason` | 为什么该片段值得触发互动，必须结合剧情内容说明；可引用弹幕共鸣作为辅助证据。 |

第一版暂不标注以下字段：

- `highlight_type`；
- `intensity`；
- `interaction_worthiness`；
- `summary`。

这些字段等标注一批样本、有足够经验后，再根据真实标注分布补充。

### 4.4 标注原则

高光点标注的对象不是普通剧情片段，而是“适合在播放器内触发低摩擦互动”的剧情瞬间。

优先标注以下片段：

- 剧情反转、身份揭露、穿越设定揭示；
- 冲突升级、威胁、争吵、误会爆发；
- 打脸、反杀、爽点、情绪释放；
- 甜蜜撒糖、暧昧、关系推进；
- 明显引发观众站队、预测、吐槽的位置。

不建议标注以下片段：

- 纯过场、铺垫、环境交代；
- 只有信息量但缺少情绪表达空间的说明；
- 弹幕很多但剧情本身不构成互动触发点的位置；
- 时间跨度过长、难以落到一个明确互动窗口的片段。

弹幕代表观众共鸣，是判断高光点的重要辅助信号。标注时可以重点观察：

- 当前时间附近弹幕是否密集；
- 是否出现强烈情绪词，例如“爽”“气死”“笑死”“离谱”“磕到了”；
- 高点赞或高分弹幕是否集中表达同一种情绪或观点；
- 弹幕是否能帮助判断该片段适合情绪表达还是观点表达。

但弹幕不能替代剧情判断。一个片段是否标为高光，最终仍要看它是否能支撑播放器内即时互动。

### 4.5 时间边界原则

`start_time` 应尽量落在情绪触发点之前或刚出现时。

`end_time` 应覆盖用户能够理解该高光的最短剧情窗口，不宜为了包含后续讨论而拉得过长。

如果一个长片段中连续出现多个独立情绪触发点，应拆成多条标注；如果多个台词共同构成一个反转或冲突，则可以合并为一条标注。

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

## 4. 高光点标注

TODO：补充人工标注规范、标注字段和验证集划分方式。

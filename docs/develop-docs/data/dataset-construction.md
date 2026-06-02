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

### 2.2 语音转写

本地视频可以先用阿里云语音识别脚本生成字幕。`--output` 参数传输出目录，脚本会把本次转写的主要产物集中写入该目录：

```bash
python scripts/transcribe_video.py /path/to/video.mp4 -o output/beipai_xunbao_biji_ep02
```

输出示例：

```text
output/beipai_xunbao_biji_ep02/video.srt
output/beipai_xunbao_biji_ep02/video.transcription.json
output/beipai_xunbao_biji_ep02/video.16k-mono.wav
```

其中 `.srt` 是后续高光识别使用的字幕，`.transcription.json` 保留阿里云原始返回结果，`.16k-mono.wav` 是转写前归一化后的音频文件，便于复查和复跑。

### 2.3 音频可视化

为了辅助观察短剧节奏和情绪强度，可以为本地视频生成音频能量图、声谱图和能量采样数据：

```bash
python scripts/generate_audio_visualization.py /path/to/video.mp4 --media-id beipai_xunbao_biji_ep02
```

输出写入：

```text
output/<media_id>/audio/energy.json
output/<media_id>/audio/waveform.svg
output/<media_id>/audio/spectrogram.png
```

- `waveform.svg`：按时间展示 RMS 音量变化，便于快速定位尖叫、争吵、静音和音乐高潮；
- `spectrogram.png`：展示频率能量分布，便于区分人声、音乐和尖锐音效；
- `energy.json`：保留每个时间采样点的 `rms_db`，后续可以和字幕、镜头切分、高光点合并到同一时间轴。

### 2.4 弹幕爬取

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

## 4. 镜头切分

镜头切分用于把本地短剧视频拆成可检查的片段，方便人工观察剧情节奏、切分质量和后续高光识别的候选窗口。

当前脚本直接接收本地视频路径，不依赖数据库或后端 API：

- 输入为本机可访问的 MP4 文件；
- 默认使用文件名 stem 作为 `video_id`；
- 对于 `ep02/video.mp4` 这类通用文件名，建议显式传入 `--video-id`，避免多个视频都输出到 `output/video/`。

运行一个视频：

```bash
python scripts/run_scene_detection.py /Users/qinminghao/Desktop/ByteDance/VideoData/raw/beipai_xunbao_biji/ep02/video.mp4 --video-id beipai_xunbao_biji_ep02
```

如果视频文件名本身就是稳定 ID，也可以省略 `--video-id`：

```bash
python scripts/run_scene_detection.py data/case1/ep01.mp4
```

可以根据切分效果调整 PySceneDetect `ContentDetector` 参数：

```bash
python scripts/run_scene_detection.py /path/to/video.mp4 --video-id demo_ep01 --threshold 24 --min-scene-len 12
```

输出写入：

```text
output/<video_id>/scene_detection.json
output/<video_id>/scenes/<video_id>_scene_001.mp4
output/<video_id>/scenes/<video_id>_scene_002.mp4
```

其中 `scene_detection.json` 记录每个片段的起止时间、帧号、timecode 和 `clip_path`；`scenes/` 下的 MP4 片段用于人工查看。生成视频片段依赖 PySceneDetect 的 `split_video_ffmpeg`，因此本机需要可用的 `ffmpeg`。

## 5. 高光候选召回

第一版高光识别采用两阶段思路：

```text
带时间戳字幕
  ↓
Stage 1: 文本 LLM 粗召回 candidate_cues
  ↓
Stage 1.5: 将 cue_time 映射到 PySceneDetect scene，生成 candidate_scene_cues
  ↓
Stage 2: 后续再接 MLLM 审核 target_scene 是否真实承载情感/价值跃迁
```

当前已实现 Stage 1 和 Stage 1.5：

```bash
python scripts/run_highlight_candidate_generation.py beipai_xunbao_biji_ep02 \
  --transcription output/beipai_xunbao_biji_ep02/video.transcription.json \
  --scene-detection output/beipai_xunbao_biji_ep02/scene_detection.json
```

输出写入：

```text
output/beipai_xunbao_biji_ep02/highlight_candidates.json
```

其中：

- `candidate_cues` 来自文本 LLM，表示“哪句台词可能位于高光镜头内”；
- `candidate_scene_cues` 是系统把 cue 的时间点映射到 PySceneDetect 切出的目标镜头；
- `target_scene` 是 Stage 2 要审核的镜头；
- `context_scene_ids` 和 `context_subtitles` 只作为 Stage 2 审核上下文，不代表整段都是高光。

可以通过 `--context-size` 控制 `target_scene` 前后各带几个相邻镜头作为审核上下文。

## 6. 高光点验证集标注

本阶段先用 `case1_ep01` 跑通验证集制作流程，不急于扩展样本规模，也不急于定义完整高光类型体系。

第一版验证集只服务一个目标：为高光点识别算法提供可重复对照的人工标注结果。后续 prompt、抽帧策略或模型选择发生变化时，可以用同一批人工标注判断识别结果是否更接近人工标准。

### 6.1 第一版流程

```text
data/case1/ep01.mp4
data/case1/ep01.srt
data/case1/ep01.json
  ↓
apps/annotation-tool/index.html
  ↓
人工标注高光点 cue_time、emotion、reason
  ↓
导出 <video_id>.annotation.json
```

第一版暂不实现自动评测脚本。标注数据格式会预留给后续评测脚本使用。

### 6.2 标注工具

当前标注工具为本地静态页面外壳，但视频、元信息和弹幕数据从后端 API 读取：

```text
apps/annotation-tool/index.html
```

标注工具不再内置固定的 `case1_ep01` 路径。进入页面后会请求：

```text
GET /api/videos
GET /api/videos/{video_id}
GET /api/videos/{video_id}/danmaku
```

其中 `stream_url` 用于设置播放器地址，`danmaku_url` 用于读取右侧弹幕时间轴。默认同源请求 API；如果后端服务和标注页不在同一个 origin，可以通过查询参数指定：

```text
http://127.0.0.1:8770/apps/annotation-tool/?api_base_url=http://127.0.0.1:8000
```

也可以指定初始视频：

```text
http://127.0.0.1:8770/apps/annotation-tool/?api_base_url=http://127.0.0.1:8000&video_id=demo_ep01
```

如果标注页本身仍通过仓库内置本地服务打开，该服务只负责托管 HTML/JS/CSS，并保留 HTTP Range 支持；实际视频 seek 能力取决于后端 `/api/videos/{video_id}/stream` 是否正确返回 `206 Partial Content`。

```bash
python scripts/serve_annotation_tool.py --port 8770
```

然后访问：

```text
http://127.0.0.1:8770/apps/annotation-tool/
```

不要直接使用 `python -m http.server` 启动标注工具。Python 标准库静态服务在当前环境下不会为 MP4 返回 `206 Partial Content`，浏览器会认为视频不可 seek，表现为进度条拖拽或按钮跳转后又回到原播放位置。

工具当前能力：

- 从后端视频列表中选择待标注视频；
- 使用视频对象中的 `stream_url` 播放视频；
- 使用视频对象中的 `danmaku_url` 读取弹幕；
- 在播放器右侧展示按时间排序的弹幕列表；
- 视频播放时自动滚动到当前时间对应的弹幕行；
- 点击弹幕行可以跳转到对应视频时间；
- 支持记录 `cue_time`；
- 支持填写 `emotion` 和 `reason`；
- 支持添加、删除标注；
- 支持导出人工标注 JSON。

### 6.3 标注字段

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
      "cue_time": 8.96,
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
| `cue_time` | 高光点时间，单位为秒。后续可映射到 PySceneDetect 切出的镜头，用于生成审核上下文和互动触发时间。 |
| `emotion` | 该高光主要激发的用户情绪。 |
| `reason` | 为什么该时间点值得触发互动，必须结合剧情内容说明；可引用弹幕共鸣作为辅助证据。 |

第一版暂不标注以下字段：

- `highlight_type`；
- `intensity`；
- `interaction_worthiness`；
- `summary`。

这些字段等标注一批样本、有足够经验后，再根据真实标注分布补充。

### 6.4 标注原则

高光点标注的对象不是普通剧情片段，而是“适合在播放器内触发低摩擦互动”的剧情瞬间。人工标注只记录一个 `cue_time`，算法侧再把这个点映射到它所在的镜头和上下文窗口。

优先标注以下片段：

- 剧情反转、身份揭露、穿越设定揭示；
- 冲突升级、威胁、争吵、误会爆发；
- 打脸、反杀、爽点、情绪释放；
- 甜蜜撒糖、暧昧、关系推进；
- 明显引发观众站队、预测、吐槽的位置。

不建议标注以下位置：

- 纯过场、铺垫、环境交代；
- 只有信息量但缺少情绪表达空间的说明；
- 弹幕很多但剧情本身不构成互动触发点的位置；
- 难以落到一个明确镜头或互动触发点的位置。

弹幕代表观众共鸣，是判断高光点的重要辅助信号。标注时可以重点观察：

- 当前时间附近弹幕是否密集；
- 是否出现强烈情绪词，例如“爽”“气死”“笑死”“离谱”“磕到了”；
- 高点赞或高分弹幕是否集中表达同一种情绪或观点；
- 弹幕是否能帮助判断该片段适合情绪表达还是观点表达。

但弹幕不能替代剧情判断。一个片段是否标为高光，最终仍要看它是否能支撑播放器内即时互动。

### 6.5 cue_time 选择原则

`cue_time` 应尽量落在情绪跃迁真正发生的台词、动作或表情上，而不是整场戏的开始时间。

如果高光由一句台词触发，优先取该句台词开始后、观众刚能理解其含义的位置。

如果高光由动作或表情触发，优先取动作完成或表情反应出现的时间点。

如果一个长片段中连续出现多个独立情绪触发点，应拆成多条标注。即使多个台词共同构成一个反转或冲突，也应选择最能代表情绪跃迁的那个 `cue_time`。

(function (root) {
  function toFiniteNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function roundTime(value) {
    return Math.round(toFiniteNumber(value, 0) * 1000) / 1000;
  }

  function formatClock(seconds) {
    const totalMs = Math.max(0, Math.round(toFiniteNumber(seconds, 0) * 1000));
    const minutes = Math.floor(totalMs / 60000);
    const secondPart = Math.floor((totalMs % 60000) / 1000);
    const ms = totalMs % 1000;
    return `${String(minutes).padStart(2, "0")}:${String(secondPart).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
  }

  function normalizeDanmaku(items) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item, index) => {
        const source = item && typeof item === "object" ? item : {};
        const text = String(source.text || "").trim();
        if (!text) return null;
        const fromSeconds = toFiniteNumber(source.time_sec, NaN);
        const fromMs = toFiniteNumber(source.time_ms, NaN);
        const timeSec = Number.isFinite(fromSeconds) ? fromSeconds : fromMs / 1000;
        if (!Number.isFinite(timeSec)) return null;
        return {
          id: String(source.danmaku_id || `danmaku_${index + 1}`),
          time_sec: roundTime(timeSec),
          text,
          digg_count: toFiniteNumber(source.digg_count, 0),
          score: toFiniteNumber(source.score, 0),
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.time_sec - b.time_sec);
  }

  function trimTrailingSlash(value) {
    return String(value || "").replace(/\/+$/, "");
  }

  function readAnnotationConfig(href) {
    const url = new URL(String(href || "http://127.0.0.1/apps/annotation-tool/"), "http://127.0.0.1");
    const apiBaseUrl = trimTrailingSlash(url.searchParams.get("api_base_url") || url.searchParams.get("apiBaseUrl") || "");
    return {
      apiBaseUrl,
      videoId: String(url.searchParams.get("video_id") || url.searchParams.get("videoId") || "").trim(),
    };
  }

  function buildApiUrl(apiBaseUrl, path) {
    const normalizedPath = String(path || "");
    if (/^https?:\/\//i.test(normalizedPath)) return normalizedPath;
    const pathWithSlash = normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`;
    const base = trimTrailingSlash(apiBaseUrl);
    return base ? `${base}${pathWithSlash}` : pathWithSlash;
  }

  function normalizeVideoList(payload) {
    const videos = Array.isArray(payload)
      ? payload
      : payload && typeof payload === "object"
        ? payload.videos || payload.episodes
        : payload;
    if (!Array.isArray(videos)) return [];
    return videos.filter((item) => item && typeof item === "object" && String(item.video_id || "").trim());
  }

  function selectInitialVideo(videos, requestedVideoId) {
    const normalizedVideos = normalizeVideoList(videos);
    if (!normalizedVideos.length) return null;
    const requested = String(requestedVideoId || "").trim();
    if (!requested) return normalizedVideos[0];
    return normalizedVideos.find((video) => String(video.video_id) === requested) || null;
  }

  function normalizeVideoContext(video, config) {
    const source = video && typeof video === "object" ? video : {};
    const currentConfig = config && typeof config === "object" ? config : {};
    const videoId = String(source.video_id || currentConfig.videoId || currentConfig.video_id || "").trim();
    const episodeApiBase = videoId ? `/api/episodes/${encodeURIComponent(videoId)}` : "";
    const isAlgorithmEpisode = Boolean(episodeApiBase && ("episode_dir" in source || "series_id" in source || "episode_id" in source));
    const streamPath = isAlgorithmEpisode
      ? `${episodeApiBase}/video`
      : source.stream_url || source.video_url || source.videoPath || source.video_path || (episodeApiBase ? `${episodeApiBase}/video` : "");
    const danmakuPath = isAlgorithmEpisode
      ? `${episodeApiBase}/danmaku`
      : source.danmaku_url || source.source_json_url || source.sourceJsonPath || source.source_json_path || (episodeApiBase ? `${episodeApiBase}/danmaku` : "");
    const subtitlePath = isAlgorithmEpisode
      ? `${episodeApiBase}/subtitle`
      : source.subtitle_url || source.subtitlePath || source.subtitle_path || (episodeApiBase ? `${episodeApiBase}/subtitle` : "");
    return {
      videoId,
      title: String(source.title || source.episode_label || videoId || "未命名视频"),
      seriesName: String(source.series_name || ""),
      episodeLabel: String(source.episode_label || ""),
      videoPath: buildApiUrl(currentConfig.apiBaseUrl, streamPath),
      subtitlePath: buildApiUrl(currentConfig.apiBaseUrl, subtitlePath),
      sourceJsonPath: buildApiUrl(currentConfig.apiBaseUrl, danmakuPath),
      raw: source,
    };
  }

  function findActiveDanmakuIndex(danmakuItems, currentTime) {
    if (!Array.isArray(danmakuItems) || danmakuItems.length === 0) return -1;
    const target = toFiniteNumber(currentTime, 0);
    let low = 0;
    let high = danmakuItems.length - 1;
    let result = -1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (danmakuItems[mid].time_sec <= target) {
        result = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return result;
  }

  function buildAnnotationPayload(config) {
    const videoId = String(config.videoId || config.video_id || "").trim();
    const annotations = Array.isArray(config.annotations) ? config.annotations : [];
    return {
      video_id: videoId,
      video_path: String(config.videoPath || config.video_path || ""),
      subtitle_path: String(config.subtitlePath || config.subtitle_path || ""),
      source_json_path: String(config.sourceJsonPath || config.source_json_path || ""),
      annotations: annotations.map((item, index) => ({
        annotation_id: `gold_${videoId}_${String(index + 1).padStart(3, "0")}`,
        cue_time: roundTime(item.cue_time),
        primary_expression: String(item.primary_expression || item.emotion || "").trim(),
        reason: String(item.reason || "").trim(),
      })),
    };
  }

  const api = {
    buildApiUrl,
    buildAnnotationPayload,
    findActiveDanmakuIndex,
    formatClock,
    normalizeVideoContext,
    normalizeVideoList,
    normalizeDanmaku,
    readAnnotationConfig,
    roundTime,
    selectInitialVideo,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.AnnotationTool = api;
})(typeof window !== "undefined" ? window : globalThis);

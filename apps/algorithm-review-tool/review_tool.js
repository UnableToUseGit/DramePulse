(function (root) {
  const VERDICTS = [
    "correct",
    "false_positive",
    "timing_early",
    "timing_late",
    "expression_wrong",
    "interaction_wrong",
  ];

  function toFiniteNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function roundTime(value) {
    return Math.round(toFiniteNumber(value, 0) * 1000) / 1000;
  }

  function cleanText(value) {
    return String(value || "").trim();
  }

  function formatClock(seconds) {
    const totalMs = Math.max(0, Math.round(toFiniteNumber(seconds, 0) * 1000));
    const minutes = Math.floor(totalMs / 60000);
    const secondPart = Math.floor((totalMs % 60000) / 1000);
    const ms = totalMs % 1000;
    return `${String(minutes).padStart(2, "0")}:${String(secondPart).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
  }

  function extractDanmakuItems(payload) {
    if (!payload || typeof payload !== "object") return [];
    const candidates = [
      payload.items,
      payload.danmaku,
      payload.danmaku && payload.danmaku.items,
      payload.comments,
    ];
    const items = candidates.find((candidate) => Array.isArray(candidate)) || [];
    return items
      .map((item, index) => {
        const source = item && typeof item === "object" ? item : {};
        const text = cleanText(source.text || source.content);
        if (!text) return null;
        const timeSec = Number.isFinite(Number(source.time_sec))
          ? Number(source.time_sec)
          : Number(source.time_ms) / 1000;
        if (!Number.isFinite(timeSec)) return null;
        return {
          id: cleanText(source.danmaku_id || source.id || `danmaku_${index + 1}`),
          time_sec: roundTime(timeSec),
          text,
          digg_count: toFiniteNumber(source.digg_count, 0),
          score: toFiniteNumber(source.score, 0),
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.time_sec - b.time_sec);
  }

  function normalizeAlgorithmOutput(payload, videoId) {
    const source = payload && typeof payload === "object" ? payload : {};
    if (Array.isArray(source.expression_triggers) && source.expression_triggers.length) {
      return source.expression_triggers.map((item, index) =>
        normalizeExpressionTrigger(item, videoId, index),
      );
    }
    if (Array.isArray(source.highlight_assets) && source.highlight_assets.length) {
      return source.highlight_assets.map((item, index) => normalizeHighlightAsset(item, videoId, index));
    }
    const candidateItems = Array.isArray(source.candidate_scene_cues) && source.candidate_scene_cues.length
      ? source.candidate_scene_cues
      : Array.isArray(source.candidate_cues) && source.candidate_cues.length
        ? source.candidate_cues
        : Array.isArray(source.highlight_cues)
          ? source.highlight_cues
          : Array.isArray(source.cues)
            ? source.cues
            : [];
    if (candidateItems.length) {
      return candidateItems.map((item, index) => normalizeHighlightCandidate(item, videoId, index));
    }
    return [];
  }

  function normalizeExpressionTrigger(item, videoId, index) {
    const source = item && typeof item === "object" ? item : {};
    const startTime = roundTime(source.start_time);
    const endTime = roundTime(source.end_time || startTime);
    const cueTime = roundTime(source.cue_time || startTime + (endTime - startTime) / 2);
    return {
      id: cleanText(source.trigger_id || `et_${videoId}_${String(index + 1).padStart(3, "0")}`),
      kind: "expression_trigger",
      start_time: startTime,
      end_time: endTime,
      cue_time: cueTime,
      source_type: cleanText(source.source_type || "plot"),
      primary_expression: cleanText(source.primary_expression || source.emotion),
      interaction_mode: cleanText(source.interaction_mode || "single_tap"),
      confidence: toFiniteNumber(source.confidence, 0),
      intensity: toFiniteNumber(source.intensity, 0),
      summary: cleanText(source.summary),
      setup: cleanText(source.setup),
      turning_point: cleanText(source.turning_point),
      expression_release: cleanText(source.expression_release),
      reason: cleanText(source.reason),
      raw: source,
    };
  }

  function normalizeHighlightAsset(item, videoId, index) {
    const source = item && typeof item === "object" ? item : {};
    const startTime = roundTime(source.start_time);
    const endTime = roundTime(source.end_time || startTime);
    return {
      id: cleanText(source.highlight_id || `h_${videoId}_${String(index + 1).padStart(3, "0")}`),
      kind: "highlight_asset",
      start_time: startTime,
      end_time: endTime,
      cue_time: roundTime(startTime + (endTime - startTime) / 2),
      source_type: cleanText(source.highlight_type || "plot"),
      primary_expression: cleanText(source.emotion),
      interaction_mode: "single_tap",
      confidence: toFiniteNumber(source.confidence, 0),
      intensity: toFiniteNumber(source.intensity, 0),
      summary: cleanText(source.summary),
      setup: cleanText(source.setup),
      turning_point: cleanText(source.turning_point),
      expression_release: cleanText(source.expression_release),
      reason: cleanText(source.reason),
      raw: source,
    };
  }

  function normalizeHighlightCandidate(item, videoId, index) {
    const source = item && typeof item === "object" ? item : {};
    const cueTime = roundTime(source.cue_time);
    const startTime = roundTime(source.context_start_time || source.start_time || cueTime);
    const endTime = roundTime(source.context_end_time || source.end_time || cueTime);
    return {
      id: cleanText(source.cue_id || `cue_${videoId}_${String(index + 1).padStart(3, "0")}`),
      kind: "highlight_candidate",
      start_time: startTime,
      end_time: endTime,
      cue_time: cueTime,
      source_type: cleanText(source.highlight_type || "plot"),
      primary_expression: "",
      interaction_mode: "single_tap",
      confidence: toFiniteNumber(source.confidence, 0),
      intensity: 0,
      summary: cleanText(source.summary || source.context_subtitles || source.utterance),
      setup: "",
      turning_point: "",
      expression_release: "",
      reason: cleanText(source.reason || "候选召回结果，需要人工判断是否适合低摩擦表达。"),
      raw: source,
    };
  }

  function normalizeReviewMap(feedback) {
    const reviews = {};
    const items = feedback && Array.isArray(feedback.trigger_reviews) ? feedback.trigger_reviews : [];
    for (const item of items) {
      if (!item || typeof item !== "object") continue;
      const triggerId = cleanText(item.trigger_id);
      if (triggerId) reviews[triggerId] = { ...item };
    }
    return reviews;
  }

  function normalizeMissedTriggers(feedback) {
    return feedback && Array.isArray(feedback.missed_triggers) ? feedback.missed_triggers.map((item) => ({ ...item })) : [];
  }

  function normalizedOptionalTime(value) {
    const text = cleanText(value);
    return text ? roundTime(text) : null;
  }

  function buildFeedbackPayload(config) {
    const videoId = cleanText(config.videoId || config.video_id);
    const reviewMap = config.reviews && typeof config.reviews === "object" ? config.reviews : {};
    const triggerReviews = Object.entries(reviewMap)
      .filter(([, review]) => review && typeof review === "object" && cleanText(review.verdict))
      .map(([triggerId, review]) => ({
        trigger_id: triggerId,
        verdict: cleanText(review.verdict),
        corrected_start_time: normalizedOptionalTime(review.corrected_start_time),
        corrected_end_time: normalizedOptionalTime(review.corrected_end_time),
        corrected_primary_expression: cleanText(review.corrected_primary_expression),
        corrected_interaction_mode: cleanText(review.corrected_interaction_mode),
        note: cleanText(review.note),
      }));
    const missedTriggers = Array.isArray(config.missedTriggers) ? config.missedTriggers : [];
    return {
      video_id: videoId,
      dataset_episode_dir: cleanText(config.datasetEpisodeDir),
      algorithm_output_path: cleanText(config.algorithmOutputPath),
      updated_at: new Date().toISOString(),
      trigger_reviews: triggerReviews,
      missed_triggers: missedTriggers.map((item, index) => ({
        missed_id: cleanText(item.missed_id || `missed_${videoId}_${String(index + 1).padStart(3, "0")}`),
        cue_time: roundTime(item.cue_time),
        source_type: cleanText(item.source_type || "plot"),
        primary_expression: cleanText(item.primary_expression),
        interaction_mode: cleanText(item.interaction_mode || "single_tap"),
        note: cleanText(item.note),
      })),
      episode_review: {
        status: cleanText(config.episodeReview && config.episodeReview.status) || "in_progress",
        note: cleanText(config.episodeReview && config.episodeReview.note),
      },
    };
  }

  const api = {
    VERDICTS,
    buildFeedbackPayload,
    extractDanmakuItems,
    formatClock,
    normalizeAlgorithmOutput,
    normalizeMissedTriggers,
    normalizeReviewMap,
    roundTime,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.ReviewTool = api;
})(typeof window !== "undefined" ? window : globalThis);

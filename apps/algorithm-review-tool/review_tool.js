(function (root) {
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
      primary_expression: cleanText(source.expression_type || source.primary_expression || source.emotion),
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

  function normalizeGoldAnnotations(payload, videoId) {
    const source = payload && typeof payload === "object" ? payload : {};
    const items = Array.isArray(source.annotations) ? source.annotations : [];
    return items
      .map((item, index) => {
        const annotation = item && typeof item === "object" ? item : {};
        const cueTime = roundTime(annotation.payoff_time || annotation.cue_time);
        if (!Number.isFinite(cueTime) || cueTime < 0) return null;
        const window = annotation.payoff_window && typeof annotation.payoff_window === "object"
          ? {
              start_time: roundTime(annotation.payoff_window.start_time),
              end_time: roundTime(annotation.payoff_window.end_time),
            }
          : null;
        return {
          id: cleanText(annotation.annotation_id || `gold_${videoId}_${String(index + 1).padStart(3, "0")}`),
          kind: "gold_annotation",
          start_time: window ? window.start_time : cueTime,
          end_time: window ? window.end_time : cueTime,
          cue_time: cueTime,
          payoff_time: cueTime,
          primary_expression: cleanText(annotation.expression_type || annotation.primary_expression),
          reason: cleanText(annotation.reason),
          payoff_window: window,
          raw: annotation,
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.cue_time - b.cue_time || a.id.localeCompare(b.id));
  }

  const api = {
    formatClock,
    normalizeAlgorithmOutput,
    normalizeGoldAnnotations,
    roundTime,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.ReviewTool = api;
})(typeof window !== "undefined" ? window : globalThis);

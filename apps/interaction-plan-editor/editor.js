const state = {
  episodes: [],
  filteredEpisodes: [],
  activeVideoId: null,
  planPayload: null,
  plan: [],
  originalPlan: [],
  duration: 0,
  activeInteractionId: null,
  dirty: false
};

const els = {
  episodeSearch: document.getElementById("episodeSearch"),
  episodeCount: document.getElementById("episodeCount"),
  episodeList: document.getElementById("episodeList"),
  activeSeries: document.getElementById("activeSeries"),
  activeTitle: document.getElementById("activeTitle"),
  durationStat: document.getElementById("durationStat"),
  planStat: document.getElementById("planStat"),
  curatedStat: document.getElementById("curatedStat"),
  video: document.getElementById("video"),
  timeReadout: document.getElementById("timeReadout"),
  activeInteractionLabel: document.getElementById("activeInteractionLabel"),
  timeline: document.getElementById("timeline"),
  interactionLayer: document.getElementById("interactionLayer"),
  playhead: document.getElementById("playhead"),
  timelineScale: document.getElementById("timelineScale"),
  interactionList: document.getElementById("interactionList"),
  saveButton: document.getElementById("saveButton"),
  addExpressionButton: document.getElementById("addExpressionButton"),
  addInnerVoiceButton: document.getElementById("addInnerVoiceButton"),
  resetButton: document.getElementById("resetButton"),
  saveStatus: document.getElementById("saveStatus"),
  interactionIdInput: document.getElementById("interactionIdInput"),
  interactionModeInput: document.getElementById("interactionModeInput"),
  triggerTimeInput: document.getElementById("triggerTimeInput"),
  durationInput: document.getElementById("durationInput"),
  expireTimeInput: document.getElementById("expireTimeInput"),
  emotionalFields: document.getElementById("emotionalFields"),
  innerVoiceFields: document.getElementById("innerVoiceFields"),
  expressionTypeInput: document.getElementById("expressionTypeInput"),
  sourceStartInput: document.getElementById("sourceStartInput"),
  sourceEndInput: document.getElementById("sourceEndInput"),
  sourceTriggerInput: document.getElementById("sourceTriggerInput"),
  innerVoiceTextInput: document.getElementById("innerVoiceTextInput"),
  candidateIdInput: document.getElementById("candidateIdInput"),
  deleteButton: document.getElementById("deleteButton"),
  formError: document.getElementById("formError")
};

const EMOTIONAL_MODE = "emotional_button";
const INNER_VOICE_MODE = "inner_voice_danmaku";
const DEFAULT_EXPRESSION_TYPE = "爽点";

function formatTime(seconds) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const secs = Math.floor(safeSeconds % 60);
  const tenths = Math.floor((safeSeconds % 1) * 10);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${tenths}`;
}

function roundTime(value) {
  return Math.round(Number(value || 0) * 1000) / 1000;
}

function pct(value) {
  if (!state.duration) return 0;
  return Math.max(0, Math.min(100, (value / state.duration) * 100));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (payload.error) message = payload.error;
    } catch (_) {
      // Keep HTTP status as fallback.
    }
    throw new Error(message);
  }
  return response.json();
}

function clonePlan(plan) {
  return JSON.parse(JSON.stringify(Array.isArray(plan) ? plan : []));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function selectedInteraction() {
  return state.plan.find((item) => item.interaction_id === state.activeInteractionId) || null;
}

function interactionLabel(item) {
  if (item?.interaction_mode === INNER_VOICE_MODE) {
    return item.content?.text || "心声";
  }
  return item?.content?.expression_type || "未知";
}

function manualIdPrefix(mode) {
  const videoId = state.activeVideoId || "video";
  return mode === INNER_VOICE_MODE ? `ivp_${videoId}_manual_` : `ip_${videoId}_manual_`;
}

function nextManualInteractionId(mode) {
  const prefix = manualIdPrefix(mode);
  let maxIndex = 0;
  for (const item of state.plan) {
    const interactionId = String(item.interaction_id || "");
    if (!interactionId.startsWith(prefix)) continue;
    const index = Number(interactionId.slice(prefix.length));
    if (Number.isInteger(index)) maxIndex = Math.max(maxIndex, index);
  }
  return `${prefix}${String(maxIndex + 1).padStart(3, "0")}`;
}

function episodeMetadata() {
  const episode = activeEpisode();
  const videoId = state.activeVideoId || "";
  const episodeMarkerIndex = videoId.lastIndexOf("_ep");
  const episodeMatch = videoId.match(/_ep(\d+)$/);
  return {
    video_id: videoId,
    series_id: episode?.series_id || (episodeMarkerIndex > 0 ? videoId.slice(0, episodeMarkerIndex) : videoId),
    episode_no: Number(episode?.episode_no || (episodeMatch ? episodeMatch[1] : 0))
  };
}

function defaultContentForMode(mode, triggerTime) {
  if (mode === INNER_VOICE_MODE) {
    return {
      text: "",
      candidate_id: ""
    };
  }
  return {
    expression_type: DEFAULT_EXPRESSION_TYPE,
    source_trigger_id: "",
    source_start_time: triggerTime,
    source_end_time: triggerTime
  };
}

function setModeFieldsVisibility(mode) {
  const isInnerVoice = mode === INNER_VOICE_MODE;
  els.emotionalFields.hidden = isInnerVoice;
  els.innerVoiceFields.hidden = !isInnerVoice;
}

function setSaveStatus(message, tone = "") {
  els.saveStatus.textContent = message;
  els.saveStatus.dataset.tone = tone;
}

function markDirty() {
  state.dirty = true;
  setSaveStatus("有未保存修改", "dirty");
  renderEpisodeList();
}

function renderEpisodeList() {
  els.episodeList.innerHTML = "";
  els.episodeCount.textContent = `${state.filteredEpisodes.length} / ${state.episodes.length} episodes`;
  for (const episode of state.filteredEpisodes) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `episode-button${episode.video_id === state.activeVideoId ? " active" : ""}`;
    button.innerHTML = `
      <div class="episode-main">
        <span>${episode.series_id}</span>
        <span>${episode.episode_id}</span>
      </div>
      <div class="episode-meta">
        ${episode.video_id} ·
        <span class="${episode.has_interaction_plan ? "badge-ready" : ""}">
          ${episode.has_interaction_plan ? `${episode.interaction_plan_count || 1} source plan` : "no plan"}
        </span>
        ${episode.has_curated_plan ? " · <span class=\"badge-curated\">curated</span>" : ""}
      </div>
    `;
    button.addEventListener("click", () => loadEpisode(episode.video_id));
    els.episodeList.appendChild(button);
  }
}

function filterEpisodes() {
  const query = els.episodeSearch.value.trim().toLowerCase();
  state.filteredEpisodes = state.episodes.filter((episode) => {
    return `${episode.video_id} ${episode.title} ${episode.series_id} ${episode.episode_id}`.toLowerCase().includes(query);
  });
  renderEpisodeList();
}

function activeEpisode() {
  return state.episodes.find((episode) => episode.video_id === state.activeVideoId) || null;
}

function renderHeader() {
  const episode = activeEpisode();
  els.activeSeries.textContent = episode ? `${episode.series_id} / ${episode.episode_id}` : "未选择";
  els.activeTitle.textContent = episode ? episode.title : "选择一个分集开始编辑";
  els.durationStat.textContent = formatTime(state.duration);
  els.planStat.textContent = `${state.plan.length} interactions`;
  const sourceCount = state.planPayload?.source_plans?.length || 0;
  els.curatedStat.textContent = state.planPayload?.has_curated_plan ? "curated" : `${sourceCount} sources`;
}

function renderTimeline() {
  els.interactionLayer.innerHTML = "";
  els.timelineScale.innerHTML = "";
  for (const item of state.plan) {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = `interaction-marker${item.interaction_id === state.activeInteractionId ? " active" : ""}`;
    marker.style.left = `${pct(Number(item.trigger_time))}%`;
    marker.title = `${item.interaction_id} · ${formatTime(Number(item.trigger_time))}`;
    marker.addEventListener("click", () => selectInteraction(item.interaction_id, { seek: true }));
    els.interactionLayer.appendChild(marker);
  }
  const marks = [0, state.duration / 2, state.duration].filter((value, index, values) => Number.isFinite(value) && values.indexOf(value) === index);
  for (const mark of marks) {
    const span = document.createElement("span");
    span.textContent = formatTime(mark);
    els.timelineScale.appendChild(span);
  }
}

function renderInteractionList() {
  els.interactionList.innerHTML = "";
  for (const item of state.plan) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `interaction-item${item.interaction_id === state.activeInteractionId ? " active" : ""}`;
    const label = interactionLabel(item);
    const sourceLabel = item._plan_source || item.interaction_mode || "curated";
    button.innerHTML = `
      <div class="interaction-main">
        <span>${escapeHtml(label)}</span>
        <span>${formatTime(Number(item.trigger_time))}</span>
      </div>
      <div class="interaction-meta">
        ${escapeHtml(sourceLabel)} · ${escapeHtml(item.interaction_id)} · duration ${Number(item.duration_sec || 0).toFixed(1)}s
      </div>
    `;
    button.addEventListener("click", () => selectInteraction(item.interaction_id, { seek: true }));
    els.interactionList.appendChild(button);
  }
}

function renderEditor() {
  const item = selectedInteraction();
  els.formError.textContent = "";
  if (!item) {
    els.interactionIdInput.value = "";
    els.interactionModeInput.value = EMOTIONAL_MODE;
    els.triggerTimeInput.value = "";
    els.durationInput.value = "";
    els.expireTimeInput.value = "";
    els.expressionTypeInput.value = DEFAULT_EXPRESSION_TYPE;
    els.sourceStartInput.value = "";
    els.sourceEndInput.value = "";
    els.sourceTriggerInput.value = "";
    els.innerVoiceTextInput.value = "";
    els.candidateIdInput.value = "";
    els.deleteButton.disabled = true;
    setModeFieldsVisibility(EMOTIONAL_MODE);
    return;
  }
  const mode = item.interaction_mode === INNER_VOICE_MODE ? INNER_VOICE_MODE : EMOTIONAL_MODE;
  els.interactionIdInput.value = item.interaction_id || "";
  els.interactionModeInput.value = mode;
  els.triggerTimeInput.value = Number(item.trigger_time || 0).toFixed(1);
  els.durationInput.value = Number(item.duration_sec || 0).toFixed(1);
  els.expireTimeInput.value = Number(item.expire_time || 0).toFixed(1);
  els.expressionTypeInput.value = item.content?.expression_type || DEFAULT_EXPRESSION_TYPE;
  els.sourceStartInput.value = Number(item.content?.source_start_time ?? item.trigger_time ?? 0).toFixed(1);
  els.sourceEndInput.value = Number(item.content?.source_end_time ?? item.trigger_time ?? 0).toFixed(1);
  els.sourceTriggerInput.value = item.content?.source_trigger_id || "";
  els.innerVoiceTextInput.value = item.content?.text || "";
  els.candidateIdInput.value = item.content?.candidate_id || "";
  els.deleteButton.disabled = false;
  setModeFieldsVisibility(mode);
}

function renderAll() {
  renderHeader();
  renderTimeline();
  renderInteractionList();
  renderEditor();
  updatePlaybackState();
}

function selectInteraction(interactionId, { seek = false } = {}) {
  state.activeInteractionId = interactionId;
  const item = selectedInteraction();
  if (seek && item) {
    els.video.currentTime = Math.max(0, Number(item.trigger_time || 0));
    els.video.play().catch(() => {});
  }
  renderAll();
}

function updatePlaybackState() {
  const currentTime = els.video.currentTime || 0;
  els.timeReadout.textContent = `${formatTime(currentTime)} / ${formatTime(state.duration)}`;
  els.playhead.style.left = `${pct(currentTime)}%`;
  const active = selectedInteraction();
  els.activeInteractionLabel.textContent = active
    ? `${active.interaction_id} · ${interactionLabel(active)}`
    : "无当前 interaction";
}

function updateSelectedFromForm({ refreshEditor = true } = {}) {
  const item = selectedInteraction();
  if (!item) return;
  els.formError.textContent = "";
  const triggerTime = Math.max(0, roundTime(els.triggerTimeInput.value));
  const durationSec = Math.max(0, roundTime(els.durationInput.value));
  const mode = els.interactionModeInput.value === INNER_VOICE_MODE ? INNER_VOICE_MODE : EMOTIONAL_MODE;
  item.trigger_time = triggerTime;
  item.duration_sec = durationSec;
  item.expire_time = roundTime(triggerTime + durationSec);
  item.interaction_mode = mode;
  if (mode === INNER_VOICE_MODE) {
    item.content = {
      text: els.innerVoiceTextInput.value,
      candidate_id: item.content?.candidate_id || els.candidateIdInput.value || ""
    };
  } else {
    item.content = {
      expression_type: els.expressionTypeInput.value || DEFAULT_EXPRESSION_TYPE,
      source_trigger_id: item.content?.source_trigger_id || els.sourceTriggerInput.value || "",
      source_start_time: Math.max(0, roundTime(els.sourceStartInput.value)),
      source_end_time: Math.max(0, roundTime(els.sourceEndInput.value))
    };
  }
  state.plan.sort((left, right) => Number(left.trigger_time) - Number(right.trigger_time) || String(left.interaction_id).localeCompare(String(right.interaction_id)));
  markDirty();
  if (refreshEditor) {
    renderAll();
  } else {
    renderHeader();
    renderTimeline();
    renderInteractionList();
    updatePlaybackState();
  }
}

function addInteraction(mode) {
  if (!state.activeVideoId) return;
  const selected = selectedInteraction();
  const triggerTime = roundTime(
    Number.isFinite(els.video.currentTime) && els.video.currentTime > 0
      ? els.video.currentTime
      : Number(selected?.trigger_time || 0)
  );
  const durationSec = 5.0;
  const metadata = episodeMetadata();
  const item = {
    interaction_id: nextManualInteractionId(mode),
    video_id: metadata.video_id,
    series_id: metadata.series_id,
    episode_no: metadata.episode_no,
    interaction_mode: mode,
    trigger_time: triggerTime,
    duration_sec: durationSec,
    expire_time: roundTime(triggerTime + durationSec),
    content: defaultContentForMode(mode, triggerTime),
    _plan_source: "manual"
  };
  state.plan.push(item);
  state.plan.sort((left, right) => Number(left.trigger_time) - Number(right.trigger_time) || String(left.interaction_id).localeCompare(String(right.interaction_id)));
  state.activeInteractionId = item.interaction_id;
  markDirty();
  renderAll();
}

function deleteSelectedInteraction() {
  const item = selectedInteraction();
  if (!item) return;
  if (!window.confirm(`确认删除 ${item.interaction_id}？`)) return;
  const currentIndex = state.plan.findIndex((candidate) => candidate.interaction_id === item.interaction_id);
  state.plan = state.plan.filter((candidate) => candidate.interaction_id !== item.interaction_id);
  const nextItem = state.plan[Math.min(currentIndex, state.plan.length - 1)] || state.plan[state.plan.length - 1] || null;
  state.activeInteractionId = nextItem?.interaction_id || null;
  markDirty();
  renderAll();
}

async function loadEpisode(videoId) {
  if (state.dirty && !window.confirm("当前修改尚未保存，确认切换分集？")) {
    return;
  }
  state.activeVideoId = videoId;
  state.dirty = false;
  state.duration = 0;
  state.planPayload = null;
  state.plan = [];
  state.originalPlan = [];
  state.activeInteractionId = null;
  els.video.src = `/api/episodes/${encodeURIComponent(videoId)}/video`;
  const payload = await fetchJson(`/api/episodes/${encodeURIComponent(videoId)}/interaction-plan`);
  state.planPayload = payload;
  state.originalPlan = clonePlan(payload.original_plan);
  state.plan = clonePlan(payload.active_plan);
  state.activeInteractionId = state.plan[0]?.interaction_id || null;
  setSaveStatus(payload.has_curated_plan ? "已加载 curated plan" : "已加载原始 plan", payload.has_curated_plan ? "saved" : "");
  renderEpisodeList();
  renderAll();
}

async function savePlan() {
  if (!state.activeVideoId) return;
  try {
    const payload = await fetchJson(`/api/episodes/${encodeURIComponent(state.activeVideoId)}/interaction-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interaction_plan: state.plan })
    });
    state.dirty = false;
    setSaveStatus(`已保存: ${payload.curated_plan_path}`, "saved");
    await refreshEpisodes();
  } catch (error) {
    setSaveStatus(`保存失败: ${error.message}`, "error");
  }
}

function resetToOriginal() {
  if (!state.originalPlan.length) return;
  if (!window.confirm("确认恢复到原始算法输出？未保存修改会丢失。")) return;
  state.plan = clonePlan(state.originalPlan);
  state.activeInteractionId = state.plan[0]?.interaction_id || null;
  markDirty();
  renderAll();
}

async function refreshEpisodes() {
  const index = await fetchJson("/api/episodes");
  state.episodes = Array.isArray(index.episodes) ? index.episodes : [];
  filterEpisodes();
}

async function init() {
  els.episodeSearch.addEventListener("input", filterEpisodes);
  els.video.addEventListener("loadedmetadata", () => {
    state.duration = Number.isFinite(els.video.duration) ? els.video.duration : 0;
    renderAll();
  });
  els.video.addEventListener("timeupdate", updatePlaybackState);
  els.saveButton.addEventListener("click", savePlan);
  els.addExpressionButton.addEventListener("click", () => addInteraction(EMOTIONAL_MODE));
  els.addInnerVoiceButton.addEventListener("click", () => addInteraction(INNER_VOICE_MODE));
  els.resetButton.addEventListener("click", resetToOriginal);
  els.deleteButton.addEventListener("click", deleteSelectedInteraction);
  els.interactionModeInput.addEventListener("change", () => updateSelectedFromForm());
  els.triggerTimeInput.addEventListener("change", updateSelectedFromForm);
  els.durationInput.addEventListener("change", updateSelectedFromForm);
  els.expressionTypeInput.addEventListener("change", updateSelectedFromForm);
  els.sourceStartInput.addEventListener("change", updateSelectedFromForm);
  els.sourceEndInput.addEventListener("change", updateSelectedFromForm);
  els.innerVoiceTextInput.addEventListener("input", () => updateSelectedFromForm({ refreshEditor: false }));
  await refreshEpisodes();
  const firstReady = state.episodes.find((episode) => episode.has_interaction_plan) || state.episodes[0];
  if (firstReady) {
    await loadEpisode(firstReady.video_id);
  }
}

init().catch((error) => {
  setSaveStatus(`加载失败: ${error.message}`, "error");
});

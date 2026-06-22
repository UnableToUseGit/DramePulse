const state = {
  episodes: [],
  filteredEpisodes: [],
  activeEpisodeId: null,
  detail: null,
  duration: 0,
  activeChapterId: null,
  goldBoundaries: [],
  finalChapterSummary: "",
  annotationDirty: false,
  annotationSaving: false
};

const els = {
  episodeSearch: document.getElementById("episodeSearch"),
  episodeCount: document.getElementById("episodeCount"),
  episodeList: document.getElementById("episodeList"),
  activeSeries: document.getElementById("activeSeries"),
  activeTitle: document.getElementById("activeTitle"),
  durationStat: document.getElementById("durationStat"),
  sceneStat: document.getElementById("sceneStat"),
  chapterStat: document.getElementById("chapterStat"),
  video: document.getElementById("video"),
  timeReadout: document.getElementById("timeReadout"),
  activeChapterLabel: document.getElementById("activeChapterLabel"),
  timeline: document.getElementById("timeline"),
  sceneLayer: document.getElementById("sceneLayer"),
  chapterLayer: document.getElementById("chapterLayer"),
  goldBoundaryLayer: document.getElementById("goldBoundaryLayer"),
  playhead: document.getElementById("playhead"),
  timelineScale: document.getElementById("timelineScale"),
  warningList: document.getElementById("warningList"),
  annotationCount: document.getElementById("annotationCount"),
  addBoundaryButton: document.getElementById("addBoundaryButton"),
  saveAnnotationButton: document.getElementById("saveAnnotationButton"),
  annotationStatus: document.getElementById("annotationStatus"),
  boundaryList: document.getElementById("boundaryList"),
  chapterList: document.getElementById("chapterList")
};

function formatTime(seconds) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const secs = Math.floor(safeSeconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
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
      // Keep the HTTP status as the fallback message.
    }
    throw new Error(message);
  }
  return response.json();
}

function normalizeGoldBoundaries(boundaries, duration) {
  const byTime = new Map();
  const rawItems = Array.isArray(boundaries) ? boundaries : [];
  for (const item of rawItems) {
    const time = Math.round(Number(item?.time) * 1000) / 1000;
    if (!Number.isFinite(time) || time <= 0 || time >= duration) continue;
    const summary = item?.ending_chapter_summary ?? item?.summary ?? item?.reason ?? "";
    byTime.set(time, {
      time,
      summary: String(summary || "").trim()
    });
  }
  return [...byTime.values()].sort((left, right) => left.time - right.time);
}

function setGoldBoundaries(boundaries, { dirty }) {
  state.goldBoundaries = normalizeGoldBoundaries(boundaries, state.duration);
  state.annotationDirty = dirty;
  renderAnnotation();
  renderTimeline();
}

function getFinalChapterSummary(annotation) {
  if (!annotation) return "";
  if (typeof annotation.final_chapter_summary === "string") {
    return annotation.final_chapter_summary.trim();
  }
  const chapters = Array.isArray(annotation.chapters) ? annotation.chapters : [];
  const finalChapter = chapters[chapters.length - 1];
  return typeof finalChapter?.summary === "string" ? finalChapter.summary.trim() : "";
}

function renderEpisodeList() {
  els.episodeList.innerHTML = "";
  els.episodeCount.textContent = `${state.filteredEpisodes.length} / ${state.episodes.length} episodes`;
  for (const episode of state.filteredEpisodes) {
    const button = document.createElement("button");
    button.className = `episode-button${episode.episode_id === state.activeEpisodeId ? " active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <div class="episode-main">
        <span>${episode.series_slug}</span>
        <span>${episode.episode_slug}</span>
      </div>
      <div class="episode-meta">
        ${formatTime(episode.duration || 0)} · ${episode.scene_count} scenes ·
        <span class="chapter-badge">${episode.has_chapters ? "chapters ready" : "no chapters"}</span>
        ${episode.has_annotation ? " · <span class=\"annotation-badge\">gold</span>" : ""}
      </div>
    `;
    button.addEventListener("click", () => loadEpisode(episode.episode_id));
    els.episodeList.appendChild(button);
  }
}

function filterEpisodes() {
  const query = els.episodeSearch.value.trim().toLowerCase();
  state.filteredEpisodes = state.episodes.filter((episode) => {
    return `${episode.series_slug} ${episode.episode_slug} ${episode.video_id}`.toLowerCase().includes(query);
  });
  renderEpisodeList();
}

function findActiveChapter(time) {
  const chapters = state.detail?.chapters || [];
  return chapters.find((chapter) => chapter.start_time <= time && time < chapter.end_time) || null;
}

function updatePlaybackState() {
  const currentTime = els.video.currentTime || 0;
  const active = findActiveChapter(currentTime);
  state.activeChapterId = active?.chapter_id || null;
  els.timeReadout.textContent = `${formatTime(currentTime)} / ${formatTime(state.duration)}`;
  els.activeChapterLabel.textContent = active ? `${active.title} · ${formatTime(active.start_time)}` : "无当前章节";
  els.playhead.style.left = `${pct(currentTime)}%`;
  document.querySelectorAll(".chapter-band, .chapter-row").forEach((node) => {
    node.classList.toggle("active", node.dataset.chapterId === state.activeChapterId);
  });
}

function seekTo(seconds) {
  els.video.currentTime = Math.max(0, seconds);
  els.video.play().catch(() => {});
  updatePlaybackState();
}

function renderTimeline() {
  els.sceneLayer.innerHTML = "";
  els.chapterLayer.innerHTML = "";
  els.goldBoundaryLayer.innerHTML = "";
  els.timelineScale.innerHTML = "";

  for (const scene of state.detail.scenes) {
    const tick = document.createElement("div");
    tick.className = "scene-tick";
    tick.style.left = `${pct(scene.start_time)}%`;
    tick.title = `${scene.scene_id} ${formatTime(scene.start_time)}-${formatTime(scene.end_time)}`;
    els.sceneLayer.appendChild(tick);
  }

  for (const chapter of state.detail.chapters) {
    const band = document.createElement("button");
    band.type = "button";
    band.className = "chapter-band";
    band.dataset.chapterId = chapter.chapter_id;
    band.style.left = `${pct(chapter.start_time)}%`;
    band.style.width = `${Math.max(0.7, pct(chapter.end_time) - pct(chapter.start_time))}%`;
    band.title = `${chapter.title} ${formatTime(chapter.start_time)}-${formatTime(chapter.end_time)}`;
    band.innerHTML = `<span>${chapter.title}</span>`;
    band.addEventListener("click", () => seekTo(chapter.start_time));
    els.chapterLayer.appendChild(band);
  }

  for (const boundary of state.goldBoundaries) {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "gold-boundary-marker";
    marker.style.left = `${pct(boundary.time)}%`;
    marker.title = `${formatTime(boundary.time)} ${boundary.summary || "人工边界"}`;
    marker.addEventListener("click", () => seekTo(boundary.time));
    els.goldBoundaryLayer.appendChild(marker);
  }

  const marks = [0, state.duration / 2, state.duration].filter((value, index, values) => {
    return Number.isFinite(value) && values.indexOf(value) === index;
  });
  for (const mark of marks) {
    const span = document.createElement("span");
    span.textContent = formatTime(mark);
    els.timelineScale.appendChild(span);
  }
}

function renderWarnings() {
  els.warningList.innerHTML = "";
  const warnings = state.detail.warnings || [];
  for (const warning of warnings) {
    const item = document.createElement("div");
    item.className = "warning-item";
    item.textContent = warning;
    els.warningList.appendChild(item);
  }
}

function setAnnotationStatus(message, tone = "") {
  els.annotationStatus.textContent = message;
  els.annotationStatus.dataset.tone = tone;
}

function markAnnotationDirty() {
  state.annotationDirty = true;
  renderAnnotationControls();
}

function renderAnnotationControls() {
  els.annotationCount.textContent = `${state.goldBoundaries.length} boundaries · ${state.goldBoundaries.length + 1} chapters`;
  els.addBoundaryButton.disabled = !state.detail || state.annotationSaving;
  els.saveAnnotationButton.disabled = !state.detail || state.annotationSaving || !state.annotationDirty;
  if (state.annotationSaving) {
    setAnnotationStatus("保存中...", "pending");
  } else if (state.annotationDirty) {
    setAnnotationStatus("有未保存修改", "dirty");
  } else if (state.detail) {
    setAnnotationStatus(state.goldBoundaries.length ? "已保存" : "未标注", state.goldBoundaries.length ? "saved" : "");
  } else {
    setAnnotationStatus("", "");
  }
}

function updateBoundarySummary(index, value) {
  if (!state.goldBoundaries[index]) return;
  state.goldBoundaries[index].summary = value.trim();
  markAnnotationDirty();
}

function updateBoundaryTime(index, value) {
  if (!state.goldBoundaries[index]) return;
  state.goldBoundaries[index].time = Number(value);
  setGoldBoundaries(state.goldBoundaries, { dirty: true });
}

function deleteBoundary(index) {
  state.goldBoundaries.splice(index, 1);
  setGoldBoundaries(state.goldBoundaries, { dirty: true });
}

function updateFinalChapterSummary(value) {
  state.finalChapterSummary = value.trim();
  markAnnotationDirty();
}

function renderAnnotation() {
  renderAnnotationControls();
  els.boundaryList.innerHTML = "";

  state.goldBoundaries.forEach((boundary, index) => {
    const row = document.createElement("div");
    row.className = "boundary-row";

    const segmentStart = index === 0 ? 0 : state.goldBoundaries[index - 1].time;
    const segment = document.createElement("button");
    segment.type = "button";
    segment.className = "boundary-segment";
    segment.textContent = `${formatTime(segmentStart)}-${formatTime(boundary.time)}`;
    segment.addEventListener("click", () => seekTo(segmentStart));

    const timeInput = document.createElement("input");
    timeInput.type = "number";
    timeInput.min = "0.1";
    timeInput.max = String(Math.max(0.1, state.duration - 0.1));
    timeInput.step = "0.1";
    timeInput.value = String(boundary.time);
    timeInput.ariaLabel = "ending boundary time";
    timeInput.addEventListener("change", () => updateBoundaryTime(index, timeInput.value));

    const summaryInput = document.createElement("input");
    summaryInput.type = "text";
    summaryInput.value = boundary.summary;
    summaryInput.placeholder = "章节摘要";
    summaryInput.ariaLabel = "ending chapter summary";
    summaryInput.addEventListener("input", () => updateBoundarySummary(index, summaryInput.value));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "boundary-remove";
    remove.textContent = "删除";
    remove.addEventListener("click", () => deleteBoundary(index));

    row.append(segment, timeInput, summaryInput, remove);
    els.boundaryList.appendChild(row);
  });

  const finalRow = document.createElement("div");
  finalRow.className = "boundary-row final-chapter-row";
  const finalStart = state.goldBoundaries.length ? state.goldBoundaries[state.goldBoundaries.length - 1].time : 0;

  const finalSegment = document.createElement("button");
  finalSegment.type = "button";
  finalSegment.className = "boundary-segment";
  finalSegment.textContent = `${formatTime(finalStart)}-${formatTime(state.duration)}`;
  finalSegment.addEventListener("click", () => seekTo(finalStart));

  const finalEnd = document.createElement("span");
  finalEnd.className = "boundary-fixed-end";
  finalEnd.textContent = formatTime(state.duration);

  const finalSummaryInput = document.createElement("input");
  finalSummaryInput.type = "text";
  finalSummaryInput.value = state.finalChapterSummary;
  finalSummaryInput.placeholder = "最后一章摘要";
  finalSummaryInput.ariaLabel = "final chapter summary";
  finalSummaryInput.addEventListener("input", () => updateFinalChapterSummary(finalSummaryInput.value));

  const spacer = document.createElement("span");
  spacer.className = "boundary-empty-action";
  finalRow.append(finalSegment, finalEnd, finalSummaryInput, spacer);
  els.boundaryList.appendChild(finalRow);
}

function renderChapters() {
  els.chapterList.innerHTML = "";
  const chapters = state.detail.chapters || [];
  if (!chapters.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "当前分集没有 story_chapters.json。可以先运行章节生成 pipeline，再通过 --chapter-output-root 指向输出目录。";
    els.chapterList.appendChild(empty);
    return;
  }
  for (const chapter of chapters) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "chapter-row";
    row.dataset.chapterId = chapter.chapter_id;
    row.innerHTML = `
      <div class="chapter-row-header">
        <span>${chapter.title}</span>
        <span class="chapter-time">${formatTime(chapter.start_time)}-${formatTime(chapter.end_time)}</span>
      </div>
      <p class="chapter-summary">${chapter.summary || "无摘要"} · importance ${chapter.importance.toFixed(2)}</p>
    `;
    row.addEventListener("click", () => seekTo(chapter.start_time));
    els.chapterList.appendChild(row);
  }
}

function renderEpisodeDetail() {
  const detail = state.detail;
  state.duration = detail.duration || els.video.duration || 0;
  state.goldBoundaries = normalizeGoldBoundaries(detail.gold_annotation?.boundaries, state.duration);
  state.finalChapterSummary = getFinalChapterSummary(detail.gold_annotation);
  state.annotationDirty = false;
  state.annotationSaving = false;
  els.activeSeries.textContent = detail.video_id;
  els.activeTitle.textContent = `${detail.series_slug} / ${detail.episode_slug}`;
  els.durationStat.textContent = formatTime(state.duration);
  els.sceneStat.textContent = `${detail.scene_count} scenes`;
  els.chapterStat.textContent = `${detail.chapter_count} chapters`;
  els.video.src = detail.media_url;
  renderEpisodeList();
  renderTimeline();
  renderWarnings();
  renderAnnotation();
  renderChapters();
  updatePlaybackState();
}

function addBoundaryAtCurrentTime() {
  if (!state.detail || !state.duration) return;
  const rawTime = Math.round((els.video.currentTime || 0) * 10) / 10;
  if (rawTime >= state.duration - 0.5) {
    setAnnotationStatus("最后一章请编辑最后一行", "dirty");
    return;
  }
  const time = Math.max(0.1, Math.min(rawTime, state.duration - 0.1));
  setGoldBoundaries([...state.goldBoundaries, { time, summary: "" }], { dirty: true });
}

async function saveAnnotation() {
  if (!state.detail || state.annotationSaving) return;
  state.annotationSaving = true;
  let saveError = null;
  renderAnnotationControls();
  try {
    const response = await fetchJson(
      `/api/episodes/${encodeURIComponent(state.activeEpisodeId)}/story-chapter-annotation`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          boundaries: state.goldBoundaries.map((boundary) => ({
            time: boundary.time,
            ending_chapter_summary: boundary.summary
          })),
          final_chapter_summary: state.finalChapterSummary
        })
      }
    );
    state.detail.gold_annotation = response.annotation;
    state.goldBoundaries = normalizeGoldBoundaries(response.annotation?.boundaries, state.duration);
    state.finalChapterSummary = getFinalChapterSummary(response.annotation);
    state.annotationDirty = false;
    const episode = state.episodes.find((item) => item.episode_id === state.activeEpisodeId);
    if (episode) episode.has_annotation = true;
    renderEpisodeList();
    renderTimeline();
    renderAnnotation();
  } catch (error) {
    saveError = error;
    state.annotationDirty = true;
  } finally {
    state.annotationSaving = false;
    renderAnnotationControls();
    if (saveError) {
      setAnnotationStatus(`保存失败：${saveError.message}`, "error");
    }
  }
}

async function loadEpisode(episodeId) {
  state.activeEpisodeId = episodeId;
  els.activeTitle.textContent = "加载分集...";
  renderEpisodeList();
  state.detail = await fetchJson(`/api/episodes/${encodeURIComponent(episodeId)}`);
  renderEpisodeDetail();
}

async function init() {
  try {
    state.episodes = await fetchJson("/api/episodes");
    state.filteredEpisodes = state.episodes;
    renderEpisodeList();
    if (state.episodes.length > 0) {
      await loadEpisode(state.episodes[0].episode_id);
    } else {
      els.activeTitle.textContent = "未发现可用分集";
    }
  } catch (error) {
    els.activeTitle.textContent = "加载失败";
    els.chapterList.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

els.episodeSearch.addEventListener("input", filterEpisodes);
els.addBoundaryButton.addEventListener("click", addBoundaryAtCurrentTime);
els.saveAnnotationButton.addEventListener("click", saveAnnotation);
els.video.addEventListener("timeupdate", updatePlaybackState);
els.video.addEventListener("loadedmetadata", () => {
  state.duration = Math.max(state.duration, els.video.duration || 0);
  renderTimeline();
  updatePlaybackState();
});
els.timeline.addEventListener("click", (event) => {
  if (event.target.closest(".chapter-band, .gold-boundary-marker")) return;
  const rect = els.timeline.getBoundingClientRect();
  const ratio = (event.clientX - rect.left) / rect.width;
  seekTo(ratio * state.duration);
});

init();

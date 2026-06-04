const state = {
  episodes: [],
  filteredEpisodes: [],
  activeEpisodeId: null,
  detail: null,
  duration: 0,
  activeChapterId: null
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
  playhead: document.getElementById("playhead"),
  timelineScale: document.getElementById("timelineScale"),
  warningList: document.getElementById("warningList"),
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

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
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
  els.activeSeries.textContent = detail.video_id;
  els.activeTitle.textContent = `${detail.series_slug} / ${detail.episode_slug}`;
  els.durationStat.textContent = formatTime(state.duration);
  els.sceneStat.textContent = `${detail.scene_count} scenes`;
  els.chapterStat.textContent = `${detail.chapter_count} chapters`;
  els.video.src = detail.media_url;
  renderEpisodeList();
  renderTimeline();
  renderWarnings();
  renderChapters();
  updatePlaybackState();
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
els.video.addEventListener("timeupdate", updatePlaybackState);
els.video.addEventListener("loadedmetadata", () => {
  state.duration = Math.max(state.duration, els.video.duration || 0);
  renderTimeline();
  updatePlaybackState();
});
els.timeline.addEventListener("click", (event) => {
  if (event.target.closest(".chapter-band")) return;
  const rect = els.timeline.getBoundingClientRect();
  const ratio = (event.clientX - rect.left) / rect.width;
  seekTo(ratio * state.duration);
});

init();

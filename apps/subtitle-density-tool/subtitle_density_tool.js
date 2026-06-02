(function () {
  const state = {
    episodes: [],
    episode: null,
    density: null,
    activeTab: "dialogue",
    activeIndex: 0,
  };

  const episodeSelect = document.getElementById("episodeSelect");
  const video = document.getElementById("video");
  const statusEl = document.getElementById("status");
  const timelineEl = document.getElementById("timeline");
  const playheadEl = document.getElementById("playhead");
  const metricsEl = document.getElementById("metrics");
  const rangeListEl = document.getElementById("rangeList");
  const prevItemBtn = document.getElementById("prevItem");
  const nextItemBtn = document.getElementById("nextItem");

  function toFiniteNumber(value, fallback = 0) {
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

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  }

  function getDuration() {
    const densityDuration = toFiniteNumber(state.density && state.density.duration_sec, 0);
    const videoDuration = Number.isFinite(video.duration) ? video.duration : 0;
    return Math.max(densityDuration, videoDuration, 1);
  }

  function rangeLeft(startTime, duration) {
    return `${Math.max(0, Math.min(100, (toFiniteNumber(startTime, 0) / duration) * 100))}%`;
  }

  function rangeWidth(startTime, endTime, duration) {
    const width = ((toFiniteNumber(endTime, 0) - toFiniteNumber(startTime, 0)) / duration) * 100;
    return `${Math.max(0.2, Math.min(100, width))}%`;
  }

  function seekTo(time) {
    video.currentTime = Math.max(0, toFiniteNumber(time, 0));
    video.play().catch(() => {});
  }

  function currentItems() {
    const density = state.density || {};
    if (state.activeTab === "silent") return Array.isArray(density.silent_ranges) ? density.silent_ranges : [];
    if (state.activeTab === "density") return Array.isArray(density.density_windows) ? density.density_windows : [];
    return Array.isArray(density.dialogue_ranges) ? density.dialogue_ranges : [];
  }

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function renderMetrics() {
    const density = state.density || {};
    const metrics = [
      ["时长", `${formatClock(density.duration_sec || 0)}`],
      ["字幕条数", density.subtitle_count || 0],
      ["对白段", density.dialogue_range_count || 0],
      ["无字幕段", density.silent_range_count || 0],
    ];
    metricsEl.innerHTML = metrics
      .map(([label, value]) => `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`)
      .join("");
  }

  function renderDensityTimeline() {
    const density = state.density || {};
    const duration = getDuration();
    const parts = ['<div class="playhead" id="playhead"></div>'];

    for (const item of density.dialogue_ranges || []) {
      parts.push(
        `<button class="range dialogue" title="对白 ${formatClock(item.start_time)} - ${formatClock(item.end_time)}" style="left:${rangeLeft(item.start_time, duration)};width:${rangeWidth(item.start_time, item.end_time, duration)}" data-time="${roundTime(item.start_time)}"></button>`,
      );
    }
    for (const item of density.silent_ranges || []) {
      parts.push(
        `<button class="range silent" title="无字幕 ${formatClock(item.start_time)} - ${formatClock(item.end_time)}" style="left:${rangeLeft(item.start_time, duration)};width:${rangeWidth(item.start_time, item.end_time, duration)}" data-time="${roundTime(item.start_time)}"></button>`,
      );
    }
    for (const item of density.density_windows || []) {
      const level = String(item.density_level || "none");
      parts.push(
        `<button class="density ${escapeHtml(level)}" title="${escapeHtml(level)} ${formatClock(item.start_time)} - ${formatClock(item.end_time)} coverage ${item.coverage_ratio}" style="left:${rangeLeft(item.start_time, duration)};width:${rangeWidth(item.start_time, item.end_time, duration)}" data-time="${roundTime(item.start_time)}"></button>`,
      );
    }
    timelineEl.innerHTML = parts.join("");
    timelineEl.querySelectorAll("[data-time]").forEach((el) => {
      el.addEventListener("click", () => seekTo(el.getAttribute("data-time")));
    });
    updatePlayhead();
  }

  function renderRangeList() {
    const items = currentItems();
    if (!items.length) {
      rangeListEl.innerHTML = '<div class="empty">没有可展示的区间。请先运行字幕密度分析脚本。</div>';
      return;
    }
    rangeListEl.innerHTML = items
      .map((item, index) => {
        const active = index === state.activeIndex ? " active" : "";
        const title = `${formatClock(item.start_time)} - ${formatClock(item.end_time)}`;
        let meta = "";
        if (state.activeTab === "density") {
          meta = `密度 ${escapeHtml(item.density_level)} ｜ 覆盖 ${item.coverage_ratio} ｜ 字/秒 ${item.chars_per_second} ｜ 字幕 ${item.subtitle_count}`;
        } else if (state.activeTab === "dialogue") {
          meta = `字幕 ${item.subtitle_count} ｜ 覆盖 ${item.coverage_ratio} ｜ 字数 ${item.char_count} ｜ 字/秒 ${item.chars_per_second}`;
        } else {
          meta = `持续 ${item.duration_sec}s`;
        }
        return `<div class="item${active}" data-index="${index}" data-time="${roundTime(item.start_time)}">
          <div class="item-title"><span>${escapeHtml(title)}</span><span class="time">${escapeHtml(item.duration_sec)}s</span></div>
          <div class="meta">${meta}</div>
        </div>`;
      })
      .join("");
    rangeListEl.querySelectorAll(".item").forEach((el) => {
      el.addEventListener("click", () => {
        state.activeIndex = Number(el.getAttribute("data-index") || 0);
        seekTo(el.getAttribute("data-time"));
        renderRangeList();
      });
    });
  }

  function renderAll() {
    renderMetrics();
    renderDensityTimeline();
    renderRangeList();
    const density = state.density || {};
    setStatus(`${state.episode ? state.episode.video_id : "未选择"} ｜ ${density._review_output_path ? "已加载密度" : "无密度文件"}`);
  }

  function updatePlayhead() {
    const duration = getDuration();
    const left = Math.max(0, Math.min(100, (video.currentTime / duration) * 100));
    const currentPlayhead = document.getElementById("playhead");
    if (currentPlayhead) currentPlayhead.style.left = `${left}%`;
  }

  async function loadEpisode(videoId) {
    state.episode = state.episodes.find((episode) => episode.video_id === videoId) || null;
    state.activeIndex = 0;
    if (!state.episode) return;
    video.src = `/api/episodes/${encodeURIComponent(videoId)}/video`;
    const density = await fetchJson(`/api/episodes/${encodeURIComponent(videoId)}/subtitle-density`);
    state.density = density;
    renderAll();
  }

  async function init() {
    setStatus("加载剧集...");
    const index = await fetchJson("/api/episodes");
    state.episodes = Array.isArray(index.episodes) ? index.episodes : [];
    episodeSelect.innerHTML = state.episodes
      .map((episode) => `<option value="${escapeHtml(episode.video_id)}">${escapeHtml(episode.video_id)} ｜ ${escapeHtml(episode.title || "")}</option>`)
      .join("");
    episodeSelect.addEventListener("change", () => loadEpisode(episodeSelect.value));
    document.querySelectorAll(".tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        state.activeTab = button.getAttribute("data-tab") || "dialogue";
        state.activeIndex = 0;
        renderRangeList();
      });
    });
    prevItemBtn.addEventListener("click", () => {
      const items = currentItems();
      if (!items.length) return;
      state.activeIndex = Math.max(0, state.activeIndex - 1);
      seekTo(items[state.activeIndex].start_time);
      renderRangeList();
    });
    nextItemBtn.addEventListener("click", () => {
      const items = currentItems();
      if (!items.length) return;
      state.activeIndex = Math.min(items.length - 1, state.activeIndex + 1);
      seekTo(items[state.activeIndex].start_time);
      renderRangeList();
    });
    video.addEventListener("timeupdate", updatePlayhead);
    video.addEventListener("loadedmetadata", updatePlayhead);
    if (state.episodes.length) {
      const params = new URLSearchParams(window.location.search);
      const requested = params.get("video_id");
      const initial = state.episodes.some((episode) => episode.video_id === requested)
        ? requested
        : state.episodes[0].video_id;
      episodeSelect.value = initial;
      await loadEpisode(initial);
    } else {
      setStatus("没有找到剧集");
    }
  }

  window.renderDensityTimeline = renderDensityTimeline;
  init().catch((error) => {
    setStatus(`加载失败：${error.message}`);
    rangeListEl.innerHTML = `<div class="empty">加载失败：${escapeHtml(error.message)}</div>`;
  });
})();

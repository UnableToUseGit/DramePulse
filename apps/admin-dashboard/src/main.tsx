import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  BarChart3,
  CircleAlert,
  Eye,
  FileImage,
  FolderPlus,
  MessageSquareText,
  MousePointerClick,
  RefreshCcw,
  Search,
  Upload,
  Video
} from "lucide-react";

import "./styles.css";

interface DashboardSummary {
  series_count: number;
  episode_count: number;
  video_count: number;
  video_ready_count: number;
  danmaku_episode_count: number;
  danmaku_count: number;
  interaction_count: number;
  event_count: number;
  vote_count: number;
  click_rate: number;
  dismiss_rate: number;
}

interface DashboardSeries {
  series_id: string;
  series_name?: string | null;
  status: string;
  episode_count: number;
  video_ready_count: number;
  danmaku_episode_count: number;
  danmaku_count: number;
  interaction_count: number;
  event_count: number;
  vote_count: number;
  asset_status: string;
}

interface DashboardVideo {
  video_id: string;
  series_id?: string | null;
  series_name?: string | null;
  title: string;
  episode_no?: number | null;
  episode_label?: string | null;
  status: string;
  interaction_count: number;
  event_count: number;
  vote_count: number;
  danmaku_count: number;
  has_danmaku: boolean;
  asset_status: string;
}

interface DashboardEvent {
  event_id: string;
  event_type: string;
  user_id: string;
  video_id: string;
  client_time: number;
  server_time: string;
}

interface DashboardPayload {
  summary: DashboardSummary;
  series: DashboardSeries[];
  videos: DashboardVideo[];
  interactions: unknown[];
  recent_events: DashboardEvent[];
}

interface SeriesSummary {
  series_id: string;
  series_name?: string | null;
  status: string;
  episode_count: number;
  min_episode_no?: number | null;
  max_episode_no?: number | null;
  name_object_key: string;
  cover_object_key: string;
}

interface SeriesEpisode {
  video_id: string;
  title: string;
  episode_no?: number | null;
  episode_label?: string | null;
  oss_bucket: string;
  oss_object_key: string;
  douyin_json_path?: string | null;
  content_type: string;
  size: number;
  status: string;
  updated_at?: string | null;
}

interface SeriesDetail {
  series: SeriesSummary;
  episodes: SeriesEpisode[];
}

interface FolderVideo {
  file: File;
  relativePath: string;
  episodeNo: number;
  episodeLabel: string;
  title: string;
}

type ActiveTab = "dashboard" | "content";

interface AuthState {
  authenticated: boolean;
  username?: string | null;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatTime(value: number): string {
  return `${value.toFixed(1)}s`;
}

function formatBytes(value: number): string {
  if (value > 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }
  if (value > 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} B`;
}

function formatCoverage(done: number, total: number): string {
  return total > 0 ? `${done}/${total}` : "0/0";
}

function assetStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    deleted: "已下架",
    ready: "完整",
    missing_video: "缺视频",
    missing_danmaku: "缺弹幕",
    missing_interaction: "缺互动"
  };
  return labels[status] || status;
}

function assetStatusClass(status: string): string {
  if (status === "deleted") {
    return "status-deleted";
  }
  return status === "ready" ? "status-ready" : "status-warning";
}

function episodeLabel(video: DashboardVideo): string {
  if (video.series_name && video.episode_label) {
    return `${video.series_name} / ${video.episode_label}`;
  }
  if (video.series_name && video.episode_no) {
    return `${video.series_name} / 第${video.episode_no}集`;
  }
  return video.series_name || video.series_id || "Demo";
}

function getRelativePath(file: File): string {
  const withPath = file as File & { webkitRelativePath?: string };
  return withPath.webkitRelativePath || file.name;
}

function inferEpisodeNo(path: string, fallback: number): number {
  const patterns = [
    /(?:^|[/_-])ep0*(\d+)(?:[/_.-]|$)/i,
    /(?:^|[/_-])e0*(\d+)(?:[/_.-]|$)/i,
    /第\s*0*(\d+)\s*集/,
    /(?:^|[/_-])0*(\d+)(?:[/_.-]|$)/
  ];
  for (const pattern of patterns) {
    const match = path.match(pattern);
    if (match?.[1]) {
      const value = Number(match[1]);
      if (Number.isFinite(value) && value > 0) {
        return value;
      }
    }
  }
  return fallback;
}

function toEpisodeLabel(episodeNo: number): string {
  return `ep${String(episodeNo).padStart(2, "0")}`;
}

function buildFolderVideos(files: FileList | null, seriesName: string): FolderVideo[] {
  const videos = Array.from(files ?? [])
    .filter((file) => file.type === "video/mp4" || file.name.toLowerCase().endsWith(".mp4"))
    .map((file, index) => {
      const relativePath = getRelativePath(file);
      const episodeNo = inferEpisodeNo(relativePath, index + 1);
      return {
        file,
        relativePath,
        episodeNo,
        episodeLabel: toEpisodeLabel(episodeNo),
        title: `${seriesName || "短剧"} 第${episodeNo}集`
      };
    })
    .sort((a, b) => a.episodeNo - b.episodeNo || a.relativePath.localeCompare(b.relativePath));

  const used = new Set<number>();
  return videos.map((video, index) => {
    if (!used.has(video.episodeNo)) {
      used.add(video.episodeNo);
      return video;
    }
    const episodeNo = index + 1;
    used.add(episodeNo);
    return {
      ...video,
      episodeNo,
      episodeLabel: toEpisodeLabel(episodeNo),
      title: `${seriesName || "短剧"} 第${episodeNo}集`
    };
  });
}

async function readResponse(response: Response): Promise<string> {
  if (response.ok) {
    return "操作成功";
  }
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : `请求失败 ${response.status}`;
  } catch {
    return `请求失败 ${response.status}`;
  }
}

async function adminFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, credentials: "same-origin" });
}

async function setSeriesOnlineState(series: { series_id: string; series_name?: string | null; status: string }): Promise<string> {
  const isDeleted = series.status === "deleted";
  const response = await adminFetch(
    isDeleted ? `/api/admin/series/${series.series_id}/restore` : `/api/admin/series/${series.series_id}`,
    { method: isDeleted ? "POST" : "DELETE" }
  );
  const text = await readResponse(response);
  if (!response.ok) {
    throw new Error(text);
  }
  return text;
}

function StatCard({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: string; hint: string }) {
  return (
    <section className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        <div className="stat-hint">{hint}</div>
      </div>
    </section>
  );
}

function LoadingView() {
  return (
    <main className="center-state">
      <RefreshCcw className="spin" size={28} />
      <span>正在加载后台数据</span>
    </main>
  );
}

function ErrorView({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="center-state">
      <CircleAlert size={30} />
      <span>{message}</span>
      <button className="primary-button" onClick={onRetry} type="button">
        <RefreshCcw size={16} />
        重试
      </button>
    </main>
  );
}

function LoginView({ onLoggedIn }: { onLoggedIn: () => Promise<void> }) {
  const [username, setUsername] = React.useState("root");
  const [password, setPassword] = React.useState("");
  const [message, setMessage] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const response = await adminFetch("/api/admin/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      if (!response.ok) {
        throw new Error(await readResponse(response));
      }
      await onLoggedIn();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={submit}>
        <div>
          <p className="eyebrow">DramePulse Admin</p>
          <h1>后台登录</h1>
        </div>
        <label>
          账号
          <input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          密码
          <input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button className="primary-button" disabled={busy || !username || !password} type="submit">
          登录
        </button>
        {message ? <div className="login-error">{message}</div> : null}
      </form>
    </main>
  );
}

function DashboardView({ data, onChanged }: { data: DashboardPayload; onChanged: () => Promise<void> }) {
  const [expandedSeriesIds, setExpandedSeriesIds] = React.useState<Set<string>>(new Set());
  const episodeRisks: DashboardVideo[] = [];
  const [seriesSearch, setSeriesSearch] = React.useState("");
  const [busySeriesId, setBusySeriesId] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const filteredSeries = data.series.filter((series) => {
    const keyword = seriesSearch.trim().toLowerCase();
    if (!keyword) {
      return true;
    }
    return `${series.series_name || ""} ${series.series_id}`.toLowerCase().includes(keyword);
  });
  function toggleSeries(seriesId: string) {
    setExpandedSeriesIds((current) => {
      const next = new Set(current);
      if (next.has(seriesId)) {
        next.delete(seriesId);
      } else {
        next.add(seriesId);
      }
      return next;
    });
  }

  function videosForSeries(seriesId: string): DashboardVideo[] {
    return data.videos.filter((video) => (video.series_id || video.video_id) === seriesId);
  }

  async function toggleSeriesStatus(series: DashboardSeries) {
    setBusySeriesId(series.series_id);
    setMessage(null);
    try {
      const text = await setSeriesOnlineState(series);
      if (text) {
        setMessage(text);
        await onChanged();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Operation failed");
    } finally {
      setBusySeriesId(null);
    }
  }

  return (
    <>
      <section className="stats-grid" aria-label="全局指标">
        <StatCard icon={<FolderPlus size={20} />} label="短剧" value={String(data.summary.series_count)} hint="series" />
        <StatCard icon={<Video size={20} />} label="剧集" value={String(data.summary.episode_count)} hint={`${data.summary.video_ready_count} 集有视频`} />
        <StatCard icon={<MessageSquareText size={20} />} label="弹幕覆盖" value={formatCoverage(data.summary.danmaku_episode_count, data.summary.episode_count)} hint={`${data.summary.danmaku_count} 条弹幕`} />
        <StatCard icon={<Activity size={20} />} label="互动方案" value={String(data.summary.interaction_count)} hint="danmaku poll" />
        <StatCard icon={<BarChart3 size={20} />} label="用户事件" value={String(data.summary.event_count)} hint={`${data.summary.vote_count} votes`} />
      </section>

      <section className="content-grid series-only-grid">
        <section className="panel videos-panel">
          <div className="panel-title">
            <h2>短剧资产健康</h2>
            <span>{filteredSeries.length}/{data.series.length}</span>
          </div>
          <label className="search-box dashboard-search">
            <Search size={15} />
            <input value={seriesSearch} onChange={(event) => setSeriesSearch(event.target.value)} placeholder="Search title or series_id" />
          </label>
          <div className="table">
            <div className="table-row table-head series-health-row">
              <span />
              <span>短剧</span>
              <span>视频</span>
              <span>弹幕</span>
              <span>弹幕数</span>
              <span>互动</span>
              <span>事件</span>
              <span>状态</span>
                          <span>Action</span>
            </div>
            {filteredSeries.map((series) => {
              const isExpanded = expandedSeriesIds.has(series.series_id);
              const episodes = isExpanded ? videosForSeries(series.series_id) : [];
              return (
                <React.Fragment key={series.series_id}>
                  <div className="table-row series-health-row">
                    <button className="expand-button" type="button" onClick={() => toggleSeries(series.series_id)} aria-label={isExpanded ? "收起剧集" : "展开剧集"}>
                      {isExpanded ? "⌄" : "›"}
                    </button>
                    <span>
                      <strong>{series.series_name || series.series_id}</strong>
                      <em>{series.series_id}</em>
                    </span>
                    <span>{formatCoverage(series.video_ready_count, series.episode_count)}</span>
                    <span>{formatCoverage(series.danmaku_episode_count, series.episode_count)}</span>
                    <span>{series.danmaku_count}</span>
                    <span>{series.interaction_count}</span>
                    <span>{series.event_count}</span>
                    <span className={assetStatusClass(series.asset_status)}>{assetStatusLabel(series.asset_status)}</span>
                    <button className="text-action-button" disabled={busySeriesId === series.series_id} onClick={() => void toggleSeriesStatus(series)} type="button">
                      {series.status === "deleted" ? "恢复上架" : "下架"}
                    </button>
                  </div>
                  {episodes.length > 0 ? (
                    <div className="series-episode-block">
                      <div className="episode-health-head">
                        <span>剧集</span>
                        <span>弹幕</span>
                        <span>互动</span>
                        <span>事件</span>
                        <span>状态</span>
                      </div>
                      {episodes.map((video) => (
                        <div className="episode-health-row nested-episode-row" key={video.video_id}>
                          <span>
                            <strong>{episodeLabel(video)}</strong>
                            <em>{video.title}</em>
                          </span>
                          <span>{video.danmaku_count}</span>
                          <span>{video.interaction_count}</span>
                          <span>{video.event_count}</span>
                          <span className={assetStatusClass(video.asset_status)}>{assetStatusLabel(video.asset_status)}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </React.Fragment>
              );
            })}
          </div>
        </section>

        <section className="panel events-panel">
          <div className="panel-title">
            <h2>待补齐剧集</h2>
            <span>{episodeRisks.length} 条</span>
          </div>
          <div className="event-list">
            {episodeRisks.length === 0 ? (
              <div className="empty-state">核心资产已完整</div>
            ) : (
              episodeRisks.map((video) => (
                <article className="event-item" key={video.video_id}>
                  <div>
                    <div className="event-type">{episodeLabel(video)}</div>
                    <div className="muted">
                      {video.title}
                    </div>
                  </div>
                  <div className="event-meta">
                    <span className={assetStatusClass(video.asset_status)}>{assetStatusLabel(video.asset_status)}</span>
                    <span>{video.danmaku_count} 弹幕</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </section>

      <section className="content-grid secondary-grid">
        <section className="panel events-panel">
          <div className="panel-title">
            <h2>最近事件</h2>
            <span>{data.recent_events.length} 条</span>
          </div>
          <div className="event-list">
            {data.recent_events.length === 0 ? (
              <div className="empty-state">暂无用户事件</div>
            ) : (
              data.recent_events.map((event) => (
                <article className="event-item" key={event.event_id}>
                  <div>
                    <div className="event-type">{event.event_type}</div>
                    <div className="muted">
                      {event.user_id} / {event.video_id}
                    </div>
                  </div>
                  <div className="event-meta">
                    <span>{formatTime(event.client_time)}</span>
                    <span>{event.server_time}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </section>
    </>
  );
}

function ContentManagementView({ onUploaded }: { onUploaded: () => Promise<void> }) {
  const [seriesList, setSeriesList] = React.useState<SeriesSummary[]>([]);
  const [seriesSearch, setSeriesSearch] = React.useState("");
  const [selectedSeriesId, setSelectedSeriesId] = React.useState("");
  const [detail, setDetail] = React.useState<SeriesDetail | null>(null);
  const [seriesIdInput, setSeriesIdInput] = React.useState("");
  const [seriesNameInput, setSeriesNameInput] = React.useState("");
  const [coverFile, setCoverFile] = React.useState<File | null>(null);
  const [folderVideos, setFolderVideos] = React.useState<FolderVideo[]>([]);
  const [danmakuFiles, setDanmakuFiles] = React.useState<Record<string, File | null>>({});
  const [message, setMessage] = React.useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const folderInputRef = React.useRef<HTMLInputElement | null>(null);
  const didInitialSelectRef = React.useRef(false);

  const selectedSeries = seriesList.find((series) => series.series_id === selectedSeriesId);
  const isDetailCurrent = detail?.series.series_id === selectedSeriesId;
  const displaySeries = isDetailCurrent ? detail.series : selectedSeries;
  const displayEpisodes = isDetailCurrent ? detail.episodes : [];
  const selectedSeriesName = displaySeries?.series_name || seriesNameInput;
  const activeSeriesId = selectedSeriesId || seriesIdInput;
  const filteredSeriesList = seriesList.filter((series) => {
    const keyword = seriesSearch.trim().toLowerCase();
    if (!keyword) {
      return true;
    }
    return `${series.series_name || ""} ${series.series_id}`.toLowerCase().includes(keyword);
  });

  const loadSeries = React.useCallback(async () => {
    const response = await adminFetch("/api/admin/series");
    if (!response.ok) {
      throw new Error(await readResponse(response));
    }
    const payload = (await response.json()) as { series: SeriesSummary[] };
    setSeriesList(payload.series);
    if (!didInitialSelectRef.current && !selectedSeriesId && payload.series[0]) {
      didInitialSelectRef.current = true;
      setSelectedSeriesId(payload.series[0].series_id);
    }
  }, [selectedSeriesId]);

  const loadDetail = React.useCallback(async (seriesId: string) => {
    if (!seriesId) {
      setDetail(null);
      return;
    }
    const response = await adminFetch(`/api/admin/series/${seriesId}`);
    if (!response.ok) {
      throw new Error(await readResponse(response));
    }
    const payload = (await response.json()) as SeriesDetail;
    setDetail(payload);
    setSeriesIdInput(payload.series.series_id);
    setSeriesNameInput(payload.series.series_name || "");
  }, []);

  React.useEffect(() => {
    void loadSeries().catch((err) => setMessage(err instanceof Error ? err.message : "短剧列表加载失败"));
  }, [loadSeries]);

  React.useEffect(() => {
    void loadDetail(selectedSeriesId).catch((err) => setMessage(err instanceof Error ? err.message : "短剧详情加载失败"));
  }, [loadDetail, selectedSeriesId]);

  React.useEffect(() => {
    const input = folderInputRef.current;
    if (!input) {
      return;
    }
    input.setAttribute("webkitdirectory", "");
    input.setAttribute("directory", "");
  }, []);

  async function reloadAll() {
    await loadSeries();
    await loadDetail(activeSeriesId);
    await onUploaded();
  }

  async function run(action: () => Promise<Response>) {
    setBusy(true);
    setMessage(null);
    setUploadProgress(null);
    try {
      const response = await action();
      const text = await readResponse(response);
      setMessage(text);
      if (response.ok) {
        await reloadAll();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadFolderVideos() {
    setBusy(true);
    setMessage(null);
    setUploadProgress(null);
    try {
      for (let index = 0; index < folderVideos.length; index += 1) {
        const item = folderVideos[index];
        setUploadProgress(`正在上传 ${index + 1}/${folderVideos.length}: ${item.relativePath}`);
        const body = new FormData();
        body.append("series_name", selectedSeriesName);
        body.append("episode_no", String(item.episodeNo));
        body.append("title", item.title);
        body.append("video", item.file);
        const response = await adminFetch(`/api/admin/series/${activeSeriesId}/episodes`, { method: "POST", body });
        if (!response.ok) {
          throw new Error(`${item.relativePath}: ${await readResponse(response)}`);
        }
      }
      setMessage(`已上传 ${folderVideos.length} 个视频`);
      setUploadProgress(null);
      setFolderVideos([]);
      await reloadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadEpisodeDanmaku(episode: SeriesEpisode) {
    const episodeLabelValue = episode.episode_label || (episode.episode_no ? toEpisodeLabel(episode.episode_no) : "");
    const file = danmakuFiles[episode.video_id];
    if (!file || !activeSeriesId || !episodeLabelValue) {
      return;
    }
    await run(() => {
      const body = new FormData();
      body.append("file", file);
      return adminFetch(`/api/admin/series/${activeSeriesId}/episodes/${episodeLabelValue}/danmaku`, { method: "POST", body });
    });
    setDanmakuFiles((current) => ({ ...current, [episode.video_id]: null }));
  }

  async function deleteSeries(series: SeriesSummary) {
    setBusy(true);
    setMessage(null);
    setUploadProgress(null);
    try {
      const text = await setSeriesOnlineState(series);
      if (!text) {
        return;
      }
      setMessage(text);
      if (selectedSeriesId === series.series_id && series.status !== "deleted") {
        setSelectedSeriesId("");
        setDetail(null);
        setSeriesIdInput("");
        setSeriesNameInput("");
        setFolderVideos([]);
        setDanmakuFiles({});
      }
      await loadSeries();
      if (selectedSeriesId === series.series_id && series.status === "deleted") {
        await loadDetail(series.series_id);
      }
      await onUploaded();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }

  function selectSeries(series: SeriesSummary) {
    setSelectedSeriesId(series.series_id);
    setSeriesIdInput(series.series_id);
    setSeriesNameInput(series.series_name || "");
    setDetail({ series, episodes: [] });
    setFolderVideos([]);
    setDanmakuFiles({});
    setMessage(null);
  }

  return (
    <section className="series-layout">
      <aside className="panel series-list">
        <div className="panel-title">
          <h2>短剧列表</h2>
          <span>{filteredSeriesList.length}/{seriesList.length}</span>
        </div>
        <label className="search-box">
          <Search size={15} />
          <input value={seriesSearch} onChange={(event) => setSeriesSearch(event.target.value)} placeholder="Search title or series_id" />
        </label>
        {seriesList.length === 0 ? <div className="empty-state">暂无短剧，先在右侧创建。</div> : null}
        {seriesList.length > 0 && filteredSeriesList.length === 0 ? <div className="empty-state">No matching series</div> : null}
        {filteredSeriesList.map((series) => (
          <div className={selectedSeriesId === series.series_id ? "series-item-row active" : "series-item-row"} key={series.series_id}>
            <button
              className="series-item"
              onClick={() => selectSeries(series)}
              type="button"
            >
              <strong>{series.series_name || series.series_id}</strong>
              <span>{series.series_id}</span>
              <em>{series.episode_count} 集</em>
            </button>
            <button
              aria-label={series.status === "deleted" ? "Restore series" : "Disable series"}
              className={series.status === "deleted" ? "text-action-button restore-action" : "text-action-button"}
              disabled={busy}
              onClick={() => void deleteSeries(series)}
              title={series.status === "deleted" ? "Restore series" : "Disable series"}
              type="button"
            >
              {series.status === "deleted" ? "恢复上架" : "下架"}
            </button>
          </div>
        ))}
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            setSelectedSeriesId("");
            setDetail(null);
            setSeriesIdInput("");
            setSeriesNameInput("");
            setFolderVideos([]);
            setDanmakuFiles({});
            setMessage(null);
          }}
        >
          <FolderPlus size={15} />
          新建短剧
        </button>
      </aside>

      <section className="detail-stack">
        <section className="panel detail-header">
          <div>
            <p className="eyebrow">Series Detail</p>
            <h2>{displaySeries?.series_name || seriesNameInput || "新建短剧"}</h2>
            <p className="muted">
              {activeSeriesId || "请输入 series_id"} / {displaySeries?.episode_count ?? 0} 集
            </p>
          </div>
          <div className="object-keys">
            <span>{displaySeries?.name_object_key || `dramas/${activeSeriesId}/name.txt`}</span>
            <span>{displaySeries?.cover_object_key || `dramas/${activeSeriesId}/cover.jpg`}</span>
          </div>
        </section>

        <section className="management-grid">
          <section className="panel form-panel">
            <div className="panel-title">
              <h2>剧名信息</h2>
              <FolderPlus size={18} />
            </div>
            <label>
              series_id
              <input value={seriesIdInput} onChange={(event) => setSeriesIdInput(event.target.value)} placeholder="tianxiadiyiwanku" />
            </label>
            <label>
              中文名
              <input value={seriesNameInput} onChange={(event) => setSeriesNameInput(event.target.value)} placeholder="天下第一纨绔" />
            </label>
            <button
              className="primary-button"
              disabled={busy || !seriesIdInput || !seriesNameInput}
              type="button"
              onClick={() =>
                run(() =>
                  adminFetch("/api/admin/series", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ series_id: seriesIdInput, series_name: seriesNameInput })
                  })
                )
              }
            >
              <Upload size={16} />
              保存 / 补写 name.txt
            </button>
          </section>

          <section className="panel form-panel">
            <div className="panel-title">
              <h2>剧封面</h2>
              <FileImage size={18} />
            </div>
            <label>
              封面文件
              <input accept="image/jpeg,image/png,image/webp" type="file" onChange={(event) => setCoverFile(event.target.files?.[0] ?? null)} />
            </label>
            <button
              className="primary-button"
              disabled={busy || !coverFile || !activeSeriesId}
              type="button"
              onClick={() =>
                run(() => {
                  const body = new FormData();
                  if (coverFile) {
                    body.append("file", coverFile);
                  }
                  return adminFetch(`/api/admin/series/${activeSeriesId}/cover`, { method: "POST", body });
                })
              }
            >
              <Upload size={16} />
              上传 / 替换 cover
            </button>
          </section>

          <section className="panel form-panel wide-panel">
            <div className="panel-title">
              <h2>剧集视频</h2>
              <Video size={18} />
            </div>
            <label>
              选择视频文件夹
              <input
                ref={folderInputRef}
                accept="video/mp4"
                multiple
                type="file"
                onChange={(event) => setFolderVideos(buildFolderVideos(event.target.files, selectedSeriesName))}
              />
            </label>
            {folderVideos.length > 0 ? (
              <div className="folder-preview">
                <div className="folder-summary">已识别 {folderVideos.length} 个 MP4 文件，将按集数顺序上传。</div>
                {folderVideos.slice(0, 12).map((video) => (
                  <div className="folder-row" key={video.relativePath}>
                    <span>{video.episodeLabel}</span>
                    <strong>{video.title}</strong>
                    <em>{video.relativePath}</em>
                  </div>
                ))}
                {folderVideos.length > 12 ? <div className="muted">还有 {folderVideos.length - 12} 个文件未展开显示</div> : null}
              </div>
            ) : (
              <div className="empty-state">请选择包含 MP4 文件的文件夹。</div>
            )}
            <button className="primary-button" disabled={busy || folderVideos.length === 0 || !activeSeriesId} type="button" onClick={uploadFolderVideos}>
              <Upload size={16} />
              上传 / 补充文件夹视频
            </button>
          </section>
        </section>

        <section className="panel">
          <div className="panel-title">
            <h2>已入库剧集</h2>
            <span>{displayEpisodes.length} 集</span>
          </div>
          <div className="table">
            <div className="table-row table-head episode-row">
              <span>集数</span>
              <span>标题</span>
              <span>视频 OSS Key</span>
              <span>弹幕</span>
              <span>操作</span>
            </div>
            {displayEpisodes.map((episode) => {
              const selectedFile = danmakuFiles[episode.video_id];
              return (
                <div className="table-row episode-row" key={episode.video_id}>
                  <span>{episode.episode_label || episode.episode_no}</span>
                  <span className="strong">{episode.title}</span>
                  <span>{episode.oss_object_key}</span>
                  <span>{episode.douyin_json_path || "未上传"}</span>
                  <span className="episode-actions">
                    <label className="icon-file-button">
                      <MessageSquareText size={15} />
                      <input
                        accept="application/json,.json"
                        type="file"
                        onChange={(event) =>
                          setDanmakuFiles((current) => ({
                            ...current,
                            [episode.video_id]: event.target.files?.[0] ?? null
                          }))
                        }
                      />
                    </label>
                    <button className="secondary-button" disabled={busy || !selectedFile} type="button" onClick={() => uploadEpisodeDanmaku(episode)}>
                      <Upload size={15} />
                      上传弹幕
                    </button>
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {uploadProgress ? <div className="panel status-panel">{uploadProgress}</div> : null}
        {message ? <div className="panel status-panel">{message}</div> : null}
      </section>
    </section>
  );
}

function App() {
  const [data, setData] = React.useState<DashboardPayload | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [auth, setAuth] = React.useState<AuthState | null>(null);
  const [activeTab, setActiveTab] = React.useState<ActiveTab>("dashboard");

  const loadAuth = React.useCallback(async (): Promise<AuthState> => {
    const response = await adminFetch("/api/admin/auth/me");
    if (!response.ok) {
      return { authenticated: false, username: null };
    }
    return (await response.json()) as AuthState;
  }, []);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await adminFetch("/api/admin/dashboard");
      if (response.status === 401) {
        setAuth({ authenticated: false, username: null });
        setData(null);
        return;
      }
      if (!response.ok) {
        throw new Error(`请求失败 ${response.status}`);
      }
      setData((await response.json()) as DashboardPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "后台数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    async function boot() {
      setLoading(true);
      try {
        const state = await loadAuth();
        setAuth(state);
        if (state.authenticated) {
          await loadData();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "登录状态检查失败");
      } finally {
        setLoading(false);
      }
    }
    void boot();
  }, [loadAuth, loadData]);

  async function handleLoggedIn() {
    setAuth({ authenticated: true, username: "root" });
    await loadData();
  }

  async function logout() {
    await adminFetch("/api/admin/auth/logout", { method: "POST" });
    setAuth({ authenticated: false, username: null });
    setData(null);
    setError(null);
  }

  if (loading && auth === null) {
    return <LoadingView />;
  }

  if (!auth?.authenticated) {
    return <LoginView onLoggedIn={handleLoggedIn} />;
  }

  if (loading && !data) {
    return <LoadingView />;
  }

  if (error && !data) {
    return <ErrorView message={error} onRetry={loadData} />;
  }

  if (!data) {
    return null;
  }

  return (
    <main className="app-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">DramePulse Admin</p>
          <h1>后台管理</h1>
        </div>
        <div className="header-actions">
          <button className="primary-button" onClick={loadData} type="button" disabled={loading}>
            <RefreshCcw size={16} />
            刷新
          </button>
          <button className="secondary-button" onClick={logout} type="button">
            退出登录
          </button>
        </div>
      </header>

      <nav className="tabs" aria-label="后台视图">
        <button className={activeTab === "dashboard" ? "tab active" : "tab"} onClick={() => setActiveTab("dashboard")} type="button">
          数据看板
        </button>
        <button className={activeTab === "content" ? "tab active" : "tab"} onClick={() => setActiveTab("content")} type="button">
          内容管理
        </button>
      </nav>

      {activeTab === "dashboard" ? <DashboardView data={data} onChanged={loadData} /> : <ContentManagementView onUploaded={loadData} />}
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

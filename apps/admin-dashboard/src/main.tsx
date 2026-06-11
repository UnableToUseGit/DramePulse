import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  BarChart3,
  ChevronDown,
  CircleAlert,
  Eye,
  FileImage,
  FolderPlus,
  GitBranch,
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
  has_cover: boolean;
  cover_url?: string | null;
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
  has_storyboard: boolean;
  asset_status: string;
  analysis_status: string;
  analysis_stage?: string | null;
  analysis_job_id?: string | null;
  analysis_result_path?: string | null;
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
  analysis_status: string;
  analysis_stage?: string | null;
  analysis_job_id?: string | null;
  analysis_result_path?: string | null;
}

interface AnalysisJob {
  job_id?: string | null;
  video_id: string;
  status: string;
  stage: string;
  output_dir?: string | null;
  result_text_path?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

interface AnalysisResult {
  video_id: string;
  job: AnalysisJob;
  content: string;
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

const VIDEO_CHUNK_SIZE = 512 * 1024;

type ActiveTab = "dashboard" | "content" | "storyGraph";

interface AuthState {
  authenticated: boolean;
  username?: string | null;
  role?: string | null;
}

interface StoryGraphSummary {
  series_id: string;
  series_name?: string | null;
  node_count: number;
  edge_count: number;
  available: boolean;
}

interface StoryGraphNode {
  id: string;
  label: string;
  entity_type: string;
  description: string;
  degree: number;
  chapter_ids: number[];
}

interface StoryGraphEdge {
  id: string;
  source: string;
  target: string;
  keywords: string;
  description: string;
  weight?: number | null;
  chapter_ids: number[];
}

interface StoryGraphDetail {
  series_id: string;
  node_count: number;
  edge_count: number;
  total_node_count: number;
  total_edge_count: number;
  nodes: StoryGraphNode[];
  edges: StoryGraphEdge[];
}

type StoryGraphSelection =
  | { type: "node"; item: StoryGraphNode }
  | { type: "edge"; item: StoryGraphEdge }
  | null;

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
  return status === "deleted" ? "下架" : "正常";
}

function assetStatusClass(status: string): string {
  if (status === "deleted") {
    return "status-deleted";
  }
  return "status-ready";
}

function analysisStatusLabel(status: string): string {
  if (status === "running") return "解析中";
  if (status === "completed") return "已解析";
  if (status === "failed") return "解析失败";
  return "未解析";
}

function analysisStatusClass(status: string): string {
  if (status === "completed") return "status-ready";
  if (status === "running") return "status-warning";
  if (status === "failed") return "status-danger";
  return "status-deleted";
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
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (payload.detail) {
      return JSON.stringify(payload.detail);
    }
    return `请求失败 ${response.status}`;
  } catch {
    return `请求失败 ${response.status}`;
  }
}

async function adminFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, credentials: "same-origin" });
}

function createUploadId(): string {
  const random = crypto.getRandomValues(new Uint32Array(4));
  return Array.from(random, (value) => value.toString(16).padStart(8, "0")).join("");
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

function DashboardView({ data, onChanged, readOnly }: { data: DashboardPayload; onChanged: () => Promise<void>; readOnly?: boolean }) {
  const [expandedSeriesIds, setExpandedSeriesIds] = React.useState<Set<string>>(new Set());
  const episodeRisks: DashboardVideo[] = [];
  const [seriesSearch, setSeriesSearch] = React.useState("");
  const [busySeriesId, setBusySeriesId] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const [previewCover, setPreviewCover] = React.useState<DashboardSeries | null>(null);
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
              <span>弹幕数</span>
              <span>互动</span>
              <span>封面</span>
              <span>状态</span>
              {readOnly ? null : <span>Action</span>}
            </div>
            {filteredSeries.map((series) => {
              const isExpanded = expandedSeriesIds.has(series.series_id);
              const episodes = isExpanded ? videosForSeries(series.series_id) : [];
              return (
                <React.Fragment key={series.series_id}>
                  <div className="table-row series-health-row">
                    <button
                      className={isExpanded ? "expand-button expanded" : "expand-button"}
                      type="button"
                      onClick={() => toggleSeries(series.series_id)}
                      aria-label={isExpanded ? "收起剧集" : "展开剧集"}
                    >
                      <ChevronDown size={16} strokeWidth={2.4} />
                    </button>
                    <span>
                      <strong>{series.series_name || series.series_id}</strong>
                      <em>{series.series_id}</em>
                    </span>
                    <span>{formatCoverage(series.video_ready_count, series.episode_count)}</span>
                    <span>{series.danmaku_count}</span>
                    <span>{series.interaction_count}</span>
                    <span>
                      {series.has_cover ? (
                        <button className="cover-link-button" type="button" onClick={() => setPreviewCover(series)}>
                          有
                        </button>
                      ) : (
                        <span className="muted">无</span>
                      )}
                    </span>
                    <span className={assetStatusClass(series.asset_status)}>{assetStatusLabel(series.asset_status)}</span>
                    {readOnly ? null : (
                      <button className="text-action-button" disabled={busySeriesId === series.series_id} onClick={() => void toggleSeriesStatus(series)} type="button">
                        {series.status === "deleted" ? "恢复上架" : "下架"}
                      </button>
                    )}
                  </div>
                  {episodes.length > 0 ? (
                    <div className="series-episode-block">
                      <div className="episode-health-head">
                        <span>剧集</span>
                        <span>弹幕</span>
                        <span>互动</span>
                        <span>雪碧图</span>
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
                          <span className={video.has_storyboard ? "status-ready" : "status-deleted"}>
                            {video.has_storyboard ? "正常" : "异常"}
                          </span>
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

      {previewCover ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setPreviewCover(null)}>
          <section className="cover-modal" role="dialog" aria-modal="true" aria-label="封面预览" onClick={(event) => event.stopPropagation()}>
            <div className="panel-title">
              <h2>{previewCover.series_name || previewCover.series_id}</h2>
              <button className="secondary-button" type="button" onClick={() => setPreviewCover(null)}>
                关闭
              </button>
            </div>
            <img
              alt={`${previewCover.series_name || previewCover.series_id} 封面`}
              className="cover-preview-image"
              src={`/api/admin/series/${previewCover.series_id}/cover`}
            />
          </section>
        </div>
      ) : null}

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
  const [analysisResult, setAnalysisResult] = React.useState<AnalysisResult | null>(null);
  const [busyAnalysisVideoId, setBusyAnalysisVideoId] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const folderInputRef = React.useRef<HTMLInputElement | null>(null);
  const didInitialSelectRef = React.useRef(false);

  const selectedSeries = seriesList.find((series) => series.series_id === selectedSeriesId);
  const isDetailCurrent = detail?.series.series_id === selectedSeriesId;
  const displaySeries = isDetailCurrent ? detail.series : selectedSeries;
  const displayEpisodes = isDetailCurrent ? detail.episodes : [];
  const activeSeriesId = selectedSeriesId || seriesIdInput;
  const selectedSeriesName = displaySeries?.series_name || seriesNameInput || activeSeriesId;
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
    if (payload.series.series_name) {
      setSeriesNameInput(payload.series.series_name);
    }
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

  React.useEffect(() => {
    if (!activeSeriesId || !displayEpisodes.some((episode) => episode.analysis_status === "running")) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadDetail(activeSeriesId).catch((err) => setMessage(err instanceof Error ? err.message : "解析状态刷新失败"));
    }, 4000);
    return () => window.clearInterval(timer);
  }, [activeSeriesId, displayEpisodes, loadDetail]);

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
        const uploadSeriesName = selectedSeriesName || seriesNameInput || activeSeriesId;
        const uploadId = createUploadId();
        const totalChunks = Math.max(1, Math.ceil(item.file.size / VIDEO_CHUNK_SIZE));
        for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
          const start = chunkIndex * VIDEO_CHUNK_SIZE;
          const chunk = item.file.slice(start, Math.min(item.file.size, start + VIDEO_CHUNK_SIZE), "video/mp4");
          setUploadProgress(`正在上传 ${index + 1}/${folderVideos.length}: ${item.relativePath} (${chunkIndex + 1}/${totalChunks})`);
          const body = new FormData();
          body.append("series_name", uploadSeriesName);
          body.append("episode_no", String(item.episodeNo));
          body.append("title", item.title);
          body.append("upload_id", uploadId);
          body.append("chunk_index", String(chunkIndex));
          body.append("total_chunks", String(totalChunks));
          body.append("total_size", String(item.file.size));
          body.append("chunk", chunk, `${item.episodeLabel}.${String(chunkIndex).padStart(5, "0")}.part`);
          const response = await adminFetch(`/api/admin/series/${activeSeriesId}/episodes/chunks`, { method: "POST", body });
          if (!response.ok) {
            throw new Error(`${item.relativePath}: ${await readResponse(response)}`);
          }
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

  async function startEpisodeAnalysis(episode: SeriesEpisode) {
    setBusyAnalysisVideoId(episode.video_id);
    setMessage(null);
    try {
      const response = await adminFetch(`/api/admin/videos/${episode.video_id}/analysis-jobs`, { method: "POST" });
      if (!response.ok) {
        throw new Error(await readResponse(response));
      }
      const job = (await response.json()) as AnalysisJob;
      setMessage(job.status === "running" ? "解析任务已启动" : "解析任务已创建");
      await loadDetail(activeSeriesId);
      await onUploaded();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "解析任务创建失败");
    } finally {
      setBusyAnalysisVideoId(null);
    }
  }

  async function viewEpisodeAnalysisResult(episode: SeriesEpisode) {
    setBusyAnalysisVideoId(episode.video_id);
    setMessage(null);
    try {
      const response = await adminFetch(`/api/admin/videos/${episode.video_id}/analysis-result`);
      if (!response.ok) {
        throw new Error(await readResponse(response));
      }
      setAnalysisResult((await response.json()) as AnalysisResult);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "解析结果读取失败");
    } finally {
      setBusyAnalysisVideoId(null);
    }
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
              <span>解析</span>
              <span>操作</span>
            </div>
            {displayEpisodes.map((episode) => {
              const selectedFile = danmakuFiles[episode.video_id];
              const isAnalysisBusy = busyAnalysisVideoId === episode.video_id || episode.analysis_status === "running";
              const canStartAnalysis = episode.analysis_status !== "running";
              const canViewAnalysis = episode.analysis_status === "completed";
              return (
                <div className="table-row episode-row" key={episode.video_id}>
                  <span>{episode.episode_label || episode.episode_no}</span>
                  <span className="strong">{episode.title}</span>
                  <span>{episode.oss_object_key}</span>
                  <span>{episode.douyin_json_path || "未上传"}</span>
                  <span className="analysis-cell">
                    <span className={analysisStatusClass(episode.analysis_status)}>
                      {analysisStatusLabel(episode.analysis_status)}
                    </span>
                    {episode.analysis_stage && episode.analysis_status === "running" ? <em>{episode.analysis_stage}</em> : null}
                  </span>
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
                    <button
                      className="secondary-button"
                      disabled={busy || isAnalysisBusy || !canStartAnalysis}
                      type="button"
                      onClick={() => startEpisodeAnalysis(episode)}
                    >
                      <Activity size={15} />
                      {episode.analysis_status === "failed" ? "重试解析" : "解析"}
                      </button>
                    <button
                      className="secondary-button"
                      disabled={busy || busyAnalysisVideoId === episode.video_id || !canViewAnalysis}
                      type="button"
                      onClick={() => viewEpisodeAnalysisResult(episode)}
                    >
                      <Eye size={15} />
                      查看
                    </button>
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {analysisResult ? (
          <div className="modal-backdrop" role="presentation" onClick={() => setAnalysisResult(null)}>
            <section className="analysis-modal" role="dialog" aria-modal="true" aria-label="解析结果" onClick={(event) => event.stopPropagation()}>
              <div className="panel-title">
                <div>
                  <h2>解析结果</h2>
                  <span>{analysisResult.job.result_text_path || analysisResult.video_id}</span>
                </div>
                <button className="secondary-button" type="button" onClick={() => setAnalysisResult(null)}>
                  关闭
                </button>
              </div>
              <pre className="analysis-result-text">{analysisResult.content}</pre>
            </section>
          </div>
        ) : null}

        {uploadProgress ? <div className="panel status-panel">{uploadProgress}</div> : null}
        {message ? <div className="panel status-panel">{message}</div> : null}
      </section>
    </section>
  );
}

type GraphNodeCategory = "person" | "location" | "organization" | "event" | "concept" | "other";

const GRAPH_NODE_CATEGORY_LABELS: Record<GraphNodeCategory, string> = {
  person: "人物",
  location: "地点",
  organization: "组织",
  event: "事件",
  concept: "概念",
  other: "其他"
};

const GRAPH_NODE_CATEGORY_COLORS: Record<GraphNodeCategory, string> = {
  person: "#8fa6f5",
  location: "#eab27a",
  organization: "#86d99a",
  event: "#84d8cf",
  concept: "#eda09a",
  other: "#f3cf66"
};

function graphNodeCategory(node: StoryGraphNode): GraphNodeCategory {
  const type = node.entity_type.toLowerCase();
  if (type.includes("person") || type.includes("people") || type.includes("human") || type.includes("role") || type.includes("人物") || type.includes("角色")) return "person";
  if (type.includes("location") || type.includes("place") || type.includes("address") || type.includes("geo") || type.includes("地点") || type.includes("位置")) return "location";
  if (type.includes("organization") || type.includes("org") || type.includes("company") || type.includes("组织") || type.includes("公司")) return "organization";
  if (type.includes("event") || type.includes("activity") || type.includes("action") || type.includes("事件") || type.includes("活动") || type.includes("行动")) return "event";
  if (type.includes("concept") || type.includes("object") || type.includes("state") || type.includes("mode") || type.includes("category") || type.includes("概念") || type.includes("对象") || type.includes("状态")) return "concept";

  const text = `${node.label} ${node.description}`.toLowerCase();
  if (/人物|角色|女性|男性|女子|男人|女人|父亲|母亲|丈夫|妻子|朋友|闺蜜|工人|包工头|汉子|女儿|儿子|男主|女主|老板|医生|名医/.test(text)) return "person";
  if (/地点|位置|住宅|别墅|工地|江边|灵堂|银行|国道|医院|家中|门外|河边|城市|海城|东北|南方/.test(text)) return "location";
  if (/组织|公司|家族|团队|银行|医院/.test(text)) return "organization";
  if (/事件|行动|计划|葬礼|婚礼|讨薪|劝解|跳河|出席|策划|揭露|对话|争吵|偷情/.test(text)) return "event";
  if (/概念|状态|原因|结果|关系|请柬|遗书|绝笔信|工钱|黑烟|绝望|惊恐|出轨|真相|阴谋|资产|遗产|工资|行为|模式/.test(text)) return "concept";
  return "other";
}

function graphNodeColor(node: StoryGraphNode): string {
  return GRAPH_NODE_CATEGORY_COLORS[graphNodeCategory(node)];
}

function graphNodeTypeLabel(node: StoryGraphNode): string {
  const category = graphNodeCategory(node);
  const rawType = node.entity_type && !["other", "unknown"].includes(node.entity_type.toLowerCase()) ? ` / ${node.entity_type}` : "";
  return `${GRAPH_NODE_CATEGORY_LABELS[category]}${rawType}`;
}

function chapterText(chapterIds: number[]): string {
  return chapterIds.length ? chapterIds.map((id) => `第${id}集`).join("、") : "未标注";
}

function truncateText(value: string, maxLength = 180): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

type GraphNodeLayout = {
  x: number;
  y: number;
  radius: number;
  labelVisible: boolean;
};

type GraphViewport = {
  scale: number;
  x: number;
  y: number;
};

const DEFAULT_GRAPH_VIEWPORT: GraphViewport = { scale: 1, x: 0, y: 0 };
const MIN_GRAPH_SCALE = 0.45;
const MAX_GRAPH_SCALE = 3.2;

function clampGraphScale(value: number): number {
  return Math.max(MIN_GRAPH_SCALE, Math.min(MAX_GRAPH_SCALE, value));
}

function buildGraphLayout(nodes: StoryGraphNode[], width: number, height: number): Map<string, GraphNodeLayout> {
  const layout = new Map<string, GraphNodeLayout>();
  if (!nodes.length) return layout;
  const sorted = [...nodes].sort((a, b) => b.degree - a.degree || a.label.localeCompare(b.label));
  const maxDegree = Math.max(...sorted.map((node) => node.degree), 1);
  const clusterX = width * 0.43;
  const clusterY = height * 0.52;
  sorted.forEach((node, index) => {
    const ring = index === 0 ? 0 : Math.ceil(Math.sqrt(index / 4.8));
    const angle = index * 2.399963229728653 + ring * 0.22;
    const distance = index === 0 ? 0 : 44 + ring * 38;
    const orbitJitter = Math.sin(index * 1.71) * 12;
    const x = clusterX + Math.cos(angle) * (distance + orbitJitter);
    const y = clusterY + Math.sin(angle) * (distance * 0.82 + orbitJitter * 0.6);
    const radius = 5.5 + Math.sqrt(node.degree / maxDegree) * 17;
    layout.set(node.id, {
      x: Math.max(46, Math.min(width - 46, x)),
      y: Math.max(86, Math.min(height - 68, y)),
      radius,
      labelVisible: index < 16 || node.degree >= maxDegree * 0.48
    });
  });
  return layout;
}

function StoryGraphCanvas({
  graph,
  selection,
  viewport,
  onSelect,
  onViewportChange
}: {
  graph: StoryGraphDetail | null;
  selection: StoryGraphSelection;
  viewport: GraphViewport;
  onSelect: (selection: StoryGraphSelection) => void;
  onViewportChange: (viewport: GraphViewport) => void;
}) {
  const width = 1480;
  const height = 760;
  const svgRef = React.useRef<SVGSVGElement | null>(null);
  const dragRef = React.useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);
  if (!graph || graph.nodes.length === 0) {
    return <div className="empty-state graph-empty">暂无知识图谱数据</div>;
  }

  const layout = buildGraphLayout(graph.nodes, width, height);
  const selectedNodeId = selection?.type === "node" ? selection.item.id : null;
  const selectedEdgeId = selection?.type === "edge" ? selection.item.id : null;
  const selectedEdge = selection?.type === "edge" ? selection.item : null;
  const neighborIds = new Set<string>();
  if (selectedNodeId) {
    graph.edges.forEach((edge) => {
      if (edge.source === selectedNodeId) neighborIds.add(edge.target);
      if (edge.target === selectedNodeId) neighborIds.add(edge.source);
    });
  }
  if (selectedEdge) {
    neighborIds.add(selectedEdge.source);
    neighborIds.add(selectedEdge.target);
  }

  function svgPoint(clientX: number, clientY: number): { x: number; y: number } | null {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    return {
      x: ((clientX - rect.left) / rect.width) * width,
      y: ((clientY - rect.top) / rect.height) * height
    };
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const point = svgPoint(event.clientX, event.clientY);
    if (!point) return;
    const nextScale = clampGraphScale(viewport.scale * (event.deltaY < 0 ? 1.12 : 0.89));
    const ratio = nextScale / viewport.scale;
    onViewportChange({
      scale: nextScale,
      x: point.x - (point.x - viewport.x) * ratio,
      y: point.y - (point.y - viewport.y) * ratio
    });
  }

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return;
    if (event.target instanceof Element && event.target.closest(".graph-node, .graph-edge")) return;
    const svg = svgRef.current;
    if (!svg) return;
    svg.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: viewport.x,
      originY: viewport.y
    };
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    const svg = svgRef.current;
    if (!drag || !svg) return;
    const rect = svg.getBoundingClientRect();
    onViewportChange({
      ...viewport,
      x: drag.originX + ((event.clientX - drag.startX) / rect.width) * width,
      y: drag.originY + ((event.clientY - drag.startY) / rect.height) * height
    });
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (svg && dragRef.current?.pointerId === event.pointerId) {
      svg.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
  }

  return (
    <svg
      ref={svgRef}
      className="story-graph-canvas"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Story knowledge graph"
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      <defs>
        <radialGradient id="graph-canvas-glow" cx="42%" cy="50%" r="58%">
          <stop offset="0%" stopColor="#fff7d8" stopOpacity="0.56" />
          <stop offset="45%" stopColor="#ffffff" stopOpacity="0.88" />
          <stop offset="100%" stopColor="#f8fafc" stopOpacity="1" />
        </radialGradient>
        <filter id="graph-node-shadow" x="-40%" y="-40%" width="180%" height="180%">
          <feDropShadow dx="0" dy="2" stdDeviation="2.2" floodColor="#b9951a" floodOpacity="0.18" />
        </filter>
      </defs>
      <rect className="graph-canvas-bg" x="0" y="0" width={width} height={height} onClick={() => onSelect(null)} />
      <g className="graph-viewport" transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}>
      {graph.edges.map((edge) => {
        const source = layout.get(edge.source);
        const target = layout.get(edge.target);
        if (!source || !target) return null;
        const isSelected = edge.id === selectedEdgeId || edge.source === selectedNodeId || edge.target === selectedNodeId;
        const isDimmed = Boolean(selectedNodeId || selectedEdgeId) && !isSelected;
        return (
          <line
            className={`graph-edge${isSelected ? " selected" : ""}${isDimmed ? " dimmed" : ""}`}
            key={edge.id}
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            onPointerDown={(event) => {
              event.stopPropagation();
              onSelect({ type: "edge", item: edge });
            }}
          />
        );
      })}
      {graph.nodes.map((node) => {
        const point = layout.get(node.id);
        if (!point) return null;
        const isSelected = node.id === selectedNodeId || (selectedEdge ? node.id === selectedEdge.source || node.id === selectedEdge.target : false);
        const isNeighbor = neighborIds.has(node.id);
        const isDimmed = Boolean(selectedNodeId || selectedEdgeId) && !isSelected && !isNeighbor;
        const showLabel = point.labelVisible || isSelected || isNeighbor;
        return (
          <g
            className={`graph-node${isSelected ? " selected" : ""}${isNeighbor ? " neighbor" : ""}${isDimmed ? " dimmed" : ""}`}
            key={node.id}
            onPointerDown={(event) => {
              event.stopPropagation();
              onSelect({ type: "node", item: node });
            }}
          >
            <circle cx={point.x} cy={point.y} r={point.radius} fill={graphNodeColor(node)} />
            {showLabel ? (
              <text className={point.labelVisible ? "graph-node-label primary" : "graph-node-label"} x={point.x + point.radius + 8} y={point.y + 4}>
                {node.label}
              </text>
            ) : null}
          </g>
        );
      })}
      </g>
    </svg>
  );
}

function StoryGraphDetailPanel({ selection }: { selection: StoryGraphSelection }) {
  if (!selection) {
    return (
      <div className="graph-detail-empty">
        <GitBranch size={22} />
        <p>点击节点或关系查看详情</p>
      </div>
    );
  }

  if (selection.type === "node") {
    const node = selection.item;
    return (
      <div className="graph-detail-card">
        <span className="badge">节点</span>
        <h3>{node.label}</h3>
        <dl>
          <dt>类型</dt>
          <dd>{graphNodeTypeLabel(node)}</dd>
          <dt>连接数</dt>
          <dd>{node.degree}</dd>
          <dt>来源集数</dt>
          <dd>{chapterText(node.chapter_ids)}</dd>
          <dt>描述</dt>
          <dd>{node.description || "无描述"}</dd>
        </dl>
      </div>
    );
  }

  const edge = selection.item;
  return (
    <div className="graph-detail-card">
      <span className="badge">关系</span>
      <h3>{edge.source} {"->"} {edge.target}</h3>
      <dl>
        <dt>关键词</dt>
        <dd>{edge.keywords || "未标注"}</dd>
        <dt>权重</dt>
        <dd>{edge.weight ?? "未标注"}</dd>
        <dt>来源集数</dt>
        <dd>{chapterText(edge.chapter_ids)}</dd>
        <dt>描述</dt>
        <dd>{edge.description || "无描述"}</dd>
      </dl>
    </div>
  );
}

function KnowledgeGraphView() {
  const [graphs, setGraphs] = React.useState<StoryGraphSummary[]>([]);
  const [selectedSeriesId, setSelectedSeriesId] = React.useState("");
  const [seriesSearch, setSeriesSearch] = React.useState("");
  const [nodeSearch, setNodeSearch] = React.useState("");
  const [graph, setGraph] = React.useState<StoryGraphDetail | null>(null);
  const [selection, setSelection] = React.useState<StoryGraphSelection>(null);
  const [viewport, setViewport] = React.useState<GraphViewport>(DEFAULT_GRAPH_VIEWPORT);
  const [loading, setLoading] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);

  const filteredGraphs = graphs.filter((item) => {
    const keyword = seriesSearch.trim().toLowerCase();
    if (!keyword) return true;
    return `${item.series_name || ""} ${item.series_id}`.toLowerCase().includes(keyword);
  });
  const selectedGraph = graphs.find((item) => item.series_id === selectedSeriesId);

  const loadGraphs = React.useCallback(async () => {
    setMessage(null);
    const response = await adminFetch("/api/admin/story-graphs");
    if (!response.ok) throw new Error(`图谱列表加载失败 ${response.status}`);
    const payload = (await response.json()) as { graphs: StoryGraphSummary[] };
    setGraphs(payload.graphs);
    if (!selectedSeriesId && payload.graphs[0]) setSelectedSeriesId(payload.graphs[0].series_id);
  }, [selectedSeriesId]);

  const loadGraph = React.useCallback(async (seriesId: string, keyword: string) => {
    if (!seriesId) {
      setGraph(null);
      return;
    }
    setLoading(true);
    setSelection(null);
    setViewport(DEFAULT_GRAPH_VIEWPORT);
    setMessage(null);
    try {
      const params = new URLSearchParams({ limit: "300" });
      if (keyword.trim()) params.set("q", keyword.trim());
      const response = await adminFetch(`/api/admin/story-graphs/${seriesId}?${params.toString()}`);
      if (!response.ok) throw new Error(`图谱加载失败 ${response.status}`);
      setGraph((await response.json()) as StoryGraphDetail);
    } catch (err) {
      setGraph(null);
      setMessage(err instanceof Error ? err.message : "图谱加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadGraphs().catch((err) => setMessage(err instanceof Error ? err.message : "图谱列表加载失败"));
  }, [loadGraphs]);

  React.useEffect(() => {
    if (selectedSeriesId) void loadGraph(selectedSeriesId, nodeSearch);
  }, [selectedSeriesId, loadGraph]);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    void loadGraph(selectedSeriesId, nodeSearch);
  }

  function zoomGraph(factor: number) {
    setViewport((current) => ({
      ...current,
      scale: clampGraphScale(current.scale * factor)
    }));
  }

  function resetGraphViewport() {
    setViewport(DEFAULT_GRAPH_VIEWPORT);
  }

  return (
    <section className="story-graph-layout lightrag-style">
      <div className="graph-floating-controls">
        <button className="graph-icon-button" type="button" onClick={() => void loadGraphs()} aria-label="刷新图谱列表">
          <RefreshCcw size={16} />
        </button>
        <label className="graph-select">
          <select value={selectedSeriesId} onChange={(event) => setSelectedSeriesId(event.target.value)}>
            {filteredGraphs.map((item) => (
              <option key={item.series_id} value={item.series_id}>
                {item.series_name || item.series_id}
              </option>
            ))}
          </select>
        </label>
        <label className="graph-search-inline">
          <Search size={16} />
          <input value={seriesSearch} onChange={(event) => setSeriesSearch(event.target.value)} placeholder="Search series..." />
        </label>
        <form className="graph-search-inline node-search" onSubmit={submitSearch}>
          <Search size={16} />
          <input value={nodeSearch} onChange={(event) => setNodeSearch(event.target.value)} placeholder="Search nodes in page..." />
        </form>
      </div>

      <div className="graph-type-legend" aria-label="knowledge graph legend">
        <span><i style={{ background: GRAPH_NODE_CATEGORY_COLORS.person }} />人物</span>
        <span><i style={{ background: GRAPH_NODE_CATEGORY_COLORS.location }} />地点</span>
        <span><i style={{ background: GRAPH_NODE_CATEGORY_COLORS.organization }} />组织</span>
        <span><i style={{ background: GRAPH_NODE_CATEGORY_COLORS.event }} />事件</span>
        <span><i style={{ background: GRAPH_NODE_CATEGORY_COLORS.concept }} />概念</span>
        <span><i style={{ background: GRAPH_NODE_CATEGORY_COLORS.other }} />其他</span>
      </div>

      <div className="graph-left-tools" aria-label="graph tools">
        <span><GitBranch size={16} /></span>
        <button type="button" onClick={() => void loadGraph(selectedSeriesId, nodeSearch)} aria-label="Refresh graph"><RefreshCcw size={16} /></button>
        <button type="button" onClick={resetGraphViewport} aria-label="Reset graph view">R</button>
        <span>+</span>
        <button type="button" onClick={() => zoomGraph(1.18)} aria-label="Zoom in graph">+</button>
        <button type="button" onClick={() => zoomGraph(0.84)} aria-label="Zoom out graph">-</button>
        <button type="button" onClick={resetGraphViewport} aria-label="Fit graph view">Fit</button>
      </div>

      {message ? <div className="graph-toast">{message}</div> : null}
      {loading ? <div className="empty-state graph-empty">图谱加载中...</div> : <StoryGraphCanvas graph={graph} selection={selection} viewport={viewport} onSelect={setSelection} onViewportChange={setViewport} />}

      <div className="graph-status-bar">
        <span>D: 3</span>
        <span>Max: 1000</span>
      </div>
      <div className="graph-connection-status">
        <i />
        Connected
      </div>

      <aside className={selection ? "graph-side-panel floating open" : "graph-side-panel floating"}>
        <div className="panel-title">
          <h2>详情</h2>
          {graph ? <span>{graph.total_node_count} 节点 / {graph.total_edge_count} 关系</span> : null}
        </div>
        <StoryGraphDetailPanel selection={selection} />
        {selection?.type === "node" && selection.item.description ? (
          <p className="graph-description-preview">{truncateText(selection.item.description)}</p>
        ) : null}
      </aside>

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
    setAuth(await loadAuth());
    await loadData();
  }

  async function logout() {
    await adminFetch("/api/admin/auth/logout", { method: "POST" });
    setAuth({ authenticated: false, username: null, role: null });
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
  const isReadOnly = auth.role === "readonly";

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
        <button className={`${activeTab === "content" ? "tab active" : "tab"}${isReadOnly ? " hidden" : ""}`} onClick={() => setActiveTab("content")} type="button">
          内容管理
        </button>
        <button className={activeTab === "storyGraph" ? "tab active" : "tab"} onClick={() => setActiveTab("storyGraph")} type="button">
          知识图谱
        </button>
      </nav>

      {activeTab === "dashboard" || (isReadOnly && activeTab === "content") ? <DashboardView data={data} onChanged={loadData} readOnly={isReadOnly} /> : null}
      {activeTab === "content" && !isReadOnly ? <ContentManagementView onUploaded={loadData} /> : null}
      {activeTab === "storyGraph" ? <KnowledgeGraphView /> : null}
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

import { sampleMobileDanmaku } from "./danmakuSampling";
import type { DanmakuItem } from "./types";

export interface ApiVideo {
  video_id: string;
  series_id?: string | null;
  series_name?: string | null;
  title: string;
  episode_no?: number | null;
  episode_label?: string | null;
  duration?: number | null;
  stream_url: string;
  danmaku_url: string;
  source?: string;
  douyin_video_id?: string | null;
}

export interface PlayerVideo {
  videoId: string;
  seriesId?: string;
  title: string;
  seriesName?: string;
  episodeNo?: number;
  episodeLabel?: string;
  duration: number;
  streamUrl: string;
  danmakuUrl: string;
}

export interface PlayerData {
  video: PlayerVideo;
  danmaku: DanmakuItem[];
}

export interface FetchLike {
  (input: string): Promise<{
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
  }>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function toOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function joinUrl(baseUrl: string, path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

export function normalizeVideo(value: unknown, apiBaseUrl: string): PlayerVideo | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const videoId = toStringValue(value.video_id);
  const title = toStringValue(value.title);
  const streamPath = toStringValue(value.stream_url);
  const danmakuPath = toStringValue(value.danmaku_url);
  if (!videoId || !title || !streamPath || !danmakuPath) {
    return undefined;
  }
  const video: PlayerVideo = {
    videoId,
    title,
    duration: toNumber(value.duration, 120),
    streamUrl: joinUrl(apiBaseUrl, streamPath),
    danmakuUrl: joinUrl(apiBaseUrl, danmakuPath)
  };
  const seriesId = toOptionalString(value.series_id);
  const seriesName = toOptionalString(value.series_name);
  const episodeNo = typeof value.episode_no === "number" ? value.episode_no : undefined;
  const episodeLabel = toOptionalString(value.episode_label);
  if (seriesId) {
    video.seriesId = seriesId;
  }
  if (seriesName) {
    video.seriesName = seriesName;
  }
  if (episodeNo !== undefined) {
    video.episodeNo = episodeNo;
  }
  if (episodeLabel) {
    video.episodeLabel = episodeLabel;
  }
  return video;
}

export function normalizeDanmakuResponse(value: unknown): DanmakuItem[] {
  if (!isRecord(value) || value.available === false || !Array.isArray(value.items)) {
    return [];
  }
  const items = value.items
    .filter(isRecord)
    .map((item) => ({
      danmaku_id: toOptionalString(item.danmaku_id),
      time_sec: toNumber(item.time_sec),
      text: toStringValue(item.text).trim(),
      digg_count: typeof item.digg_count === "number" ? item.digg_count : undefined,
      score: typeof item.score === "number" ? item.score : undefined
    }))
    .filter((item) => item.text.length > 0)
    .sort((a, b) => a.time_sec - b.time_sec);
  return sampleMobileDanmaku(items);
}

async function fetchJson(fetcher: FetchLike, url: string): Promise<unknown> {
  const response = await fetcher(url);
  if (!response.ok) {
    throw new Error(`Request failed ${response.status}: ${url}`);
  }
  return response.json();
}

export async function loadPlayerData({
  apiBaseUrl,
  fetcher = fetch
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
}): Promise<PlayerData> {
  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher });
  const video = videos[0];
  if (!video) {
    throw new Error("No playable videos returned by API");
  }
  return {
    video,
    danmaku: await loadVideoDanmaku({ danmakuUrl: video.danmakuUrl, fetcher })
  };
}

export async function loadPlayerVideos({
  apiBaseUrl,
  fetcher = fetch
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
}): Promise<PlayerVideo[]> {
  const videosPayload = await fetchJson(fetcher, joinUrl(apiBaseUrl, "/api/videos"));
  const rawVideos = isRecord(videosPayload) && Array.isArray(videosPayload.videos) ? videosPayload.videos : [];
  const videos = rawVideos
    .map((item) => normalizeVideo(item, apiBaseUrl))
    .filter((video): video is PlayerVideo => video !== undefined);
  if (videos.length === 0) {
    throw new Error("No playable videos returned by API");
  }
  return videos;
}

export async function loadVideoDanmaku({
  danmakuUrl,
  fetcher = fetch
}: {
  danmakuUrl: string;
  fetcher?: FetchLike;
}): Promise<DanmakuItem[]> {
  const danmakuPayload = await fetchJson(fetcher, danmakuUrl);
  return normalizeDanmakuResponse(danmakuPayload);
}

import { sampleMobileDanmaku } from "./danmakuSampling";
import {
  normalizeStoryboardManifest,
  normalizeStoryChapters,
  StoryboardManifest,
  StoryChapter
} from "./storyNavigation";
import type { DanmakuItem } from "./types";

export const DEFAULT_API_REQUEST_TIMEOUT_MS = 8000;

export interface ApiVideo {
  video_id: string;
  series_id?: string | null;
  series_name?: string | null;
  title: string;
  description?: string | null;
  synopsis?: string | null;
  episode_no?: number | null;
  episode_label?: string | null;
  duration?: number | null;
  stream_url: string;
  danmaku_url: string;
  story_chapters?: unknown;
  storyboard?: unknown;
  source?: string;
  douyin_video_id?: string | null;
}

export interface PlayerVideo {
  videoId: string;
  seriesId?: string;
  title: string;
  plotSummary: string;
  seriesName?: string;
  episodeNo?: number;
  episodeLabel?: string;
  duration: number;
  streamUrl: string;
  danmakuUrl: string;
  storyChapters?: StoryChapter[];
  storyboard?: StoryboardManifest;
}

export interface PlayerData {
  video: PlayerVideo;
  danmaku: DanmakuItem[];
}

export interface FetchLike {
  (input: string, init?: { signal?: AbortSignal }): Promise<{
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
  }>;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
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

export function joinUrl(baseUrl: string, path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

function buildPlotSummary({
  title,
  description,
  synopsis
}: {
  title: string;
  description?: string;
  synopsis?: string;
}) {
  const explicitSummary = synopsis || description;
  if (explicitSummary) {
    return explicitSummary;
  }
  return title;
}

function resolveStoryboardUrls(storyboard: StoryboardManifest, apiBaseUrl: string): StoryboardManifest {
  return {
    ...storyboard,
    sheets: storyboard.sheets.map((sheet) => ({
      ...sheet,
      url: joinUrl(apiBaseUrl, sheet.url)
    }))
  };
}

export function normalizeVideo(value: unknown, apiBaseUrl: string): PlayerVideo | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const videoId = toStringValue(value.video_id);
  const seriesId = toOptionalString(value.series_id);
  const rawTitle = toStringValue(value.title);
  const seriesName = toOptionalString(value.series_name);
  const episodeLabel = toOptionalString(value.episode_label);
  const displayTitle = seriesName || rawTitle;
  const streamPath = toStringValue(value.stream_url);
  const danmakuPath = toStringValue(value.danmaku_url);
  if (!videoId || !rawTitle || !streamPath || !danmakuPath) {
    return undefined;
  }
  const video: PlayerVideo = {
    videoId,
    ...(seriesId ? { seriesId } : {}),
    title: displayTitle,
    plotSummary: buildPlotSummary({
      title: rawTitle,
      description: toOptionalString(value.description),
      synopsis: toOptionalString(value.synopsis)
    }),
    ...(seriesName ? { seriesName } : {}),
    ...(typeof value.episode_no === "number" ? { episodeNo: value.episode_no } : {}),
    ...(episodeLabel ? { episodeLabel } : {}),
    duration: toNumber(value.duration, 120),
    streamUrl: joinUrl(apiBaseUrl, streamPath),
    danmakuUrl: joinUrl(apiBaseUrl, danmakuPath)
  };
  const storyChapters = normalizeStoryChapters(value.story_chapters ?? value.storyChapters);
  const storyboard = normalizeStoryboardManifest(value.storyboard);
  if (storyChapters.length > 0) {
    video.storyChapters = storyChapters;
  }
  if (storyboard) {
    video.storyboard = resolveStoryboardUrls(storyboard, apiBaseUrl);
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

export async function fetchJson(
  fetcher: FetchLike,
  url: string,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
): Promise<unknown> {
  const abortController = typeof AbortController !== "undefined" ? new AbortController() : undefined;
  const timeoutId =
    abortController && timeoutMs > 0
      ? setTimeout(() => {
          abortController.abort();
        }, timeoutMs)
      : undefined;
  try {
    const response = await fetcher(url, abortController ? { signal: abortController.signal } : undefined);
    if (!response.ok) {
      throw new Error(`Request failed ${response.status}: ${url}`);
    }
    return response.json();
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs}ms: ${url}`);
    }
    throw error;
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
  }
}

export async function loadPlayerData({
  apiBaseUrl,
  fetcher = fetch,
  timeoutMs
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<PlayerData> {
  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher, timeoutMs });
  const video = videos[0];
  if (!video) {
    throw new Error("No playable videos returned by API");
  }
  return {
    video,
    danmaku: await loadVideoDanmaku({ danmakuUrl: video.danmakuUrl, fetcher, timeoutMs })
  };
}

export async function loadPlayerVideos({
  apiBaseUrl,
  fetcher = fetch,
  timeoutMs
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<PlayerVideo[]> {
  const videosPayload = await fetchJson(fetcher, joinUrl(apiBaseUrl, "/api/videos"), timeoutMs);
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
  fetcher = fetch,
  timeoutMs
}: {
  danmakuUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<DanmakuItem[]> {
  const danmakuPayload = await fetchJson(fetcher, danmakuUrl, timeoutMs);
  return normalizeDanmakuResponse(danmakuPayload);
}

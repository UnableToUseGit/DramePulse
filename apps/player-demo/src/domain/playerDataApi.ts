import {
  DEFAULT_API_REQUEST_TIMEOUT_MS,
  fetchJson,
  FetchLike,
  isRecord,
  joinUrl,
  loadPlayerVideos,
  normalizeVideo,
  PlayerVideo
} from "./playerApi";
import { groupVideosBySeries } from "./playerFeed";

function extractVideosPayload(payload: unknown) {
  return isRecord(payload) && Array.isArray(payload.videos) ? payload.videos : [];
}

function normalizeVideosPayload(payload: unknown, apiBaseUrl: string) {
  return extractVideosPayload(payload)
    .map((item) => normalizeVideo(item, apiBaseUrl))
    .filter((video): video is PlayerVideo => video !== undefined);
}

function selectFirstEpisodePerSeries(videos: PlayerVideo[]) {
  return groupVideosBySeries(videos)
    .map((series) => series.episodes[0])
    .filter((video): video is PlayerVideo => video !== undefined);
}

export interface PlayerSeriesSummary {
  seriesKey: string;
  seriesId?: string;
  title: string;
  summary: string;
  episodeCount: number;
  firstVideoId?: string;
  coverUrl?: string;
  coverVideo?: PlayerVideo;
}

function toOptionalString(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function toNumber(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function isPseudoSeriesId(seriesId: string | undefined) {
  return seriesId === undefined || /^ep_\d+$/i.test(seriesId);
}

function normalizeSeriesSummary(value: unknown, apiBaseUrl: string): PlayerSeriesSummary | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const seriesId = toOptionalString(value.series_id);
  if (isPseudoSeriesId(seriesId)) {
    return undefined;
  }
  const title = toOptionalString(value.title);
  if (!title) {
    return undefined;
  }
  const coverUrl = toOptionalString(value.cover_url);
  return {
    seriesKey: `id:${seriesId}`,
    seriesId,
    title,
    summary: toOptionalString(value.summary) ?? title,
    episodeCount: toNumber(value.episode_count, 0),
    firstVideoId: toOptionalString(value.first_video_id),
    ...(coverUrl ? { coverUrl: joinUrl(apiBaseUrl, coverUrl) } : {})
  };
}

export async function loadHomeFeedVideos({
  apiBaseUrl,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}) {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, "/api/feed/home"), timeoutMs);
    const videos = normalizeVideosPayload(payload, apiBaseUrl);
    if (videos.length > 0) {
      return selectFirstEpisodePerSeries(videos);
    }
  } catch {
    // Fall back to the stable legacy endpoint while the cloud feed API is still settling.
  }
  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher, timeoutMs });
  return selectFirstEpisodePerSeries(videos);
}

export async function loadTheaterSeries({
  apiBaseUrl,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}) {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, "/api/series"), timeoutMs);
    const rawSeries = isRecord(payload) && Array.isArray(payload.series) ? payload.series : [];
    const series = rawSeries
      .map((item) => normalizeSeriesSummary(item, apiBaseUrl))
      .filter((item): item is PlayerSeriesSummary => item !== undefined);
    if (series.length > 0) {
      return series;
    }
  } catch {
    // Fall back to grouping legacy videos.
  }
  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher, timeoutMs });
  return groupVideosBySeries(videos).map((group) => ({
    seriesKey: group.seriesKey,
    seriesId: group.coverVideo.seriesId,
    title: group.title,
    summary: group.summary,
    episodeCount: group.episodeCount,
    firstVideoId: group.coverVideo.videoId,
    coverVideo: group.coverVideo
  }));
}

export async function loadSeriesEpisodes({
  apiBaseUrl,
  seriesId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  seriesId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}) {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, `/api/series/${seriesId}/episodes`), timeoutMs);
    const rawEpisodes = isRecord(payload) && Array.isArray(payload.episodes) ? payload.episodes : [];
    const episodes = rawEpisodes
      .map((item) => normalizeVideo(item, apiBaseUrl))
      .filter((video): video is PlayerVideo => video !== undefined);
    if (episodes.length > 0) {
      return episodes;
    }
  } catch {
    // Fall back to filtering the legacy all-video list.
  }
  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher, timeoutMs });
  const series = groupVideosBySeries(videos).find((group) => group.coverVideo.seriesId === seriesId);
  return series?.episodes ?? [];
}

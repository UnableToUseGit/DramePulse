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
import { groupVideosBySeries, SeriesGroup } from "./playerFeed";
import { normalizeStoryboardManifest, StoryboardManifest } from "./storyNavigation";

function extractVideosPayload(payload: unknown) {
  return isRecord(payload) && Array.isArray(payload.videos) ? payload.videos : [];
}

function normalizeVideosPayload(payload: unknown, apiBaseUrl: string) {
  return extractVideosPayload(payload)
    .map((item) => normalizeVideo(item, apiBaseUrl))
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

function withSeriesMetadata(group: SeriesGroup | undefined, series: PlayerSeriesSummary): SeriesGroup | undefined {
  if (!group) {
    return undefined;
  }
  return {
    ...group,
    title: series.title,
    summary: series.summary,
    episodeCount: series.episodeCount || group.episodeCount,
    ...(series.coverUrl ? { coverUrl: series.coverUrl } : {})
  };
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

export async function loadHomeFeedVideos({
  apiBaseUrl,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}) {
  const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, "/api/feed/home"), timeoutMs);
  return normalizeVideosPayload(payload, apiBaseUrl);
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

async function loadLegacySeriesGroups({
  apiBaseUrl,
  fetcher,
  timeoutMs
}: {
  apiBaseUrl: string;
  fetcher: FetchLike;
  timeoutMs: number;
}) {
  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher, timeoutMs });
  return groupVideosBySeries(videos);
}

export async function loadTheaterSeriesGroups({
  apiBaseUrl,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<SeriesGroup[]> {
  try {
    const seriesSummaries = await loadTheaterSeries({ apiBaseUrl, fetcher, timeoutMs });
    const groups = (
      await Promise.all(
        seriesSummaries.map(async (series) => {
          if (!series.seriesId) {
            return undefined;
          }
          const episodes = await loadSeriesEpisodes({
            apiBaseUrl,
            seriesId: series.seriesId,
            fetcher,
            timeoutMs
          });
          return withSeriesMetadata(groupVideosBySeries(episodes)[0], series);
        })
      )
    ).filter((series): series is SeriesGroup => series !== undefined);
    if (groups.length > 0) {
      return groups;
    }
  } catch {
    // Fall back to grouping the legacy all-video list.
  }
  return loadLegacySeriesGroups({ apiBaseUrl, fetcher, timeoutMs });
}

async function loadPlaybackVideo({
  apiBaseUrl,
  videoId,
  fetcher,
  timeoutMs
}: {
  apiBaseUrl: string;
  videoId: string;
  fetcher: FetchLike;
  timeoutMs: number;
}) {
  try {
    const videoPayload = await fetchJson(fetcher, joinUrl(apiBaseUrl, `/api/videos/${videoId}`), timeoutMs);
    const video = normalizeVideo(videoPayload, apiBaseUrl);
    if (video) {
      return video;
    }
  } catch {
    // Fall back to the legacy video list when the detail endpoint is unavailable or unstable.
  }

  const videos = await loadPlayerVideos({ apiBaseUrl, fetcher, timeoutMs });
  const video = videos.find((item) => item.videoId === videoId);
  if (!video) {
    throw new Error(`No playable video returned by API: ${videoId}`);
  }
  return video;
}

export interface LightweightPlaybackAssets {
  video: PlayerVideo;
  storyChapters: NonNullable<PlayerVideo["storyChapters"]>;
  storyboard?: PlayerVideo["storyboard"];
  interactionPlans: unknown[];
}

export async function loadVideoStoryboard({
  apiBaseUrl,
  videoId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  videoId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<StoryboardManifest | undefined> {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, `/api/videos/${videoId}/storyboard`), timeoutMs);
    if (isRecord(payload) && payload.available === false) {
      return undefined;
    }
    const storyboard = normalizeStoryboardManifest(payload);
    return storyboard ? resolveStoryboardUrls(storyboard, apiBaseUrl) : undefined;
  } catch {
    return undefined;
  }
}

export async function loadVideoInteractionPlans({
  apiBaseUrl,
  videoId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  videoId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<unknown[]> {
  try {
    const plansPayload = await fetchJson(
      fetcher,
      joinUrl(apiBaseUrl, `/api/videos/${videoId}/interaction-plans`),
      timeoutMs
    );
    return isRecord(plansPayload) && Array.isArray(plansPayload.interaction_plans)
      ? plansPayload.interaction_plans
      : [];
  } catch {
    return [];
  }
}

export async function loadLightweightPlaybackAssets({
  apiBaseUrl,
  videoId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  videoId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<LightweightPlaybackAssets> {
  const video = await loadPlaybackVideo({ apiBaseUrl, videoId, fetcher, timeoutMs });
  const storyboard = await loadVideoStoryboard({ apiBaseUrl, videoId, fetcher, timeoutMs });
  const enhancedVideo: PlayerVideo = storyboard ? { ...video, storyboard } : video;

  const interactionPlans = await loadVideoInteractionPlans({
    apiBaseUrl,
    videoId,
    fetcher,
    timeoutMs
  });

  return {
    video: enhancedVideo,
    storyChapters: enhancedVideo.storyChapters ?? [],
    storyboard: enhancedVideo.storyboard,
    interactionPlans
  };
}

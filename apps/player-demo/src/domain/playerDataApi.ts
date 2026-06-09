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
import type { RoleCommerceFeedAd } from "./roleCommerceAds";
import { normalizeStoryboardManifest, normalizeStoryChapters, StoryboardManifest, StoryChapter } from "./storyNavigation";

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

function normalizeSeriesAdSlot(value: unknown, apiBaseUrl: string): RoleCommerceFeedAd | undefined {
  if (!isRecord(value) || value.status === "inactive" || !isRecord(value.ad)) {
    return undefined;
  }
  const ad = value.ad;
  const adId = toOptionalString(ad.ad_id);
  const productName = toOptionalString(ad.product_name);
  if (!adId || !productName) {
    return undefined;
  }
  const streamPath = toOptionalString(ad.stream_url) ?? toOptionalString(ad.video_url);
  const productDescription = toOptionalString(ad.product_description) ?? productName;
  const characterName = toOptionalString(ad.character_name) ?? "";
  const afterEpisodeNo = toNumber(value.after_episode_no, Number.NaN);
  return {
    adId,
    campaignId: toOptionalString(value.slot_id) ?? adId,
    placement: "after_video",
    ...(Number.isFinite(afterEpisodeNo) && afterEpisodeNo > 0 ? { afterEpisodeNo } : {}),
    sponsorLabel: toOptionalString(ad.sponsor_label) ?? "广告",
    characterName,
    productName,
    title: productName,
    hook: productDescription,
    productDescription,
    voiceoverLines: [],
    sellingPoints: Array.isArray(ad.selling_points) ? ad.selling_points.filter((item): item is string => typeof item === "string") : [],
    priceText: toOptionalString(ad.price_text) ?? "",
    ctaText: toOptionalString(ad.cta_text) ?? "查看同款",
    ...(streamPath ? { streamUrl: joinUrl(apiBaseUrl, streamPath) } : {}),
    ...(Number.isFinite(toNumber(ad.duration, Number.NaN)) ? { duration: toNumber(ad.duration) } : {})
  };
}

export async function loadSeriesAdSlots({
  apiBaseUrl,
  seriesId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  seriesId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<RoleCommerceFeedAd[]> {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, `/api/series/${seriesId}/ad-slots`), timeoutMs);
    const rawSlots = isRecord(payload) && Array.isArray(payload.slots) ? payload.slots : [];
    return rawSlots
      .map((slot) => normalizeSeriesAdSlot(slot, apiBaseUrl))
      .filter((slot): slot is RoleCommerceFeedAd => slot !== undefined);
  } catch {
    return [];
  }
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
  interactionAssets: InteractionAsset[];
}

export interface InteractionAsset {
  interactionId: string;
  videoId?: string;
  interactionMode?: string;
  triggerTime: number;
  expireTime?: number;
  durationSec?: number;
  content?: Record<string, unknown>;
  sourceAssetId?: string;
  status?: string;
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

function normalizeInteractionAssets(value: unknown): InteractionAsset[] {
  if (!isRecord(value) || value.available === false || !Array.isArray(value.items)) {
    return [];
  }
  return value.items
    .filter(isRecord)
    .map((item) => {
      const interactionId = toOptionalString(item.interaction_id) ?? toOptionalString(item.interactionId);
      const triggerTime = toNumber(item.trigger_time ?? item.triggerTime, Number.NaN);
      if (!interactionId || !Number.isFinite(triggerTime)) {
        return undefined;
      }
      const content = isRecord(item.content) ? item.content : undefined;
      return {
        interactionId,
        ...(toOptionalString(item.video_id) ? { videoId: toOptionalString(item.video_id) } : {}),
        ...(toOptionalString(item.interaction_mode) ? { interactionMode: toOptionalString(item.interaction_mode) } : {}),
        triggerTime,
        ...(Number.isFinite(toNumber(item.expire_time ?? item.expireTime, Number.NaN))
          ? { expireTime: toNumber(item.expire_time ?? item.expireTime) }
          : {}),
        ...(Number.isFinite(toNumber(item.duration_sec ?? item.durationSec, Number.NaN))
          ? { durationSec: toNumber(item.duration_sec ?? item.durationSec) }
          : {}),
        ...(content ? { content } : {}),
        ...(toOptionalString(item.source_asset_id) ? { sourceAssetId: toOptionalString(item.source_asset_id) } : {}),
        ...(toOptionalString(item.status) ? { status: toOptionalString(item.status) } : {})
      };
    })
    .filter((item): item is InteractionAsset => item !== undefined)
    .sort((a, b) => a.triggerTime - b.triggerTime);
}

export async function loadVideoInteractionAssets({
  apiBaseUrl,
  videoId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  videoId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<InteractionAsset[]> {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, `/api/videos/${videoId}/interaction-assets`), timeoutMs);
    return normalizeInteractionAssets(payload);
  } catch {
    return [];
  }
}

export async function loadVideoStoryChapters({
  apiBaseUrl,
  videoId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS
}: {
  apiBaseUrl: string;
  videoId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
}): Promise<StoryChapter[]> {
  try {
    const payload = await fetchJson(fetcher, joinUrl(apiBaseUrl, `/api/videos/${videoId}/story-chapters`), timeoutMs);
    if (isRecord(payload) && payload.available === false) {
      return [];
    }
    return normalizeStoryChapters(isRecord(payload) ? payload.chapters : undefined);
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
  const [storyboard, storyChaptersFromEndpoint, interactionAssets] = await Promise.all([
    loadVideoStoryboard({ apiBaseUrl, videoId, fetcher, timeoutMs }),
    loadVideoStoryChapters({ apiBaseUrl, videoId, fetcher, timeoutMs }),
    loadVideoInteractionAssets({ apiBaseUrl, videoId, fetcher, timeoutMs })
  ]);
  const storyChapters = storyChaptersFromEndpoint.length > 0 ? storyChaptersFromEndpoint : video.storyChapters ?? [];
  const enhancedVideo: PlayerVideo = {
    ...video,
    ...(storyboard ? { storyboard } : {}),
    ...(storyChapters.length > 0 ? { storyChapters } : {})
  };

  return {
    video: enhancedVideo,
    storyChapters,
    storyboard: enhancedVideo.storyboard,
    interactionPlans: [],
    interactionAssets
  };
}

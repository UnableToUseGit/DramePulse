import { Image } from "react-native";
import { DEFAULT_API_REQUEST_TIMEOUT_MS, FetchLike } from "./playerApi";
import { loadVideoInteractionPlans, loadVideoStoryboard } from "./playerDataApi";
import type { PlaybackAssetCache } from "./playbackAssetCache";
import type { StoryboardManifest } from "./storyNavigation";

export interface PrefetchableSeriesCover {
  coverUrl?: string;
}

export type ImagePrefetcher = (url: string) => Promise<boolean>;

const DEFAULT_SERIES_COVER_PREFETCH_LIMIT = 6;

export async function prefetchStoryboardSheets({
  cache,
  videoId,
  storyboard,
  limit,
  prefetchImage = Image.prefetch
}: {
  cache: PlaybackAssetCache;
  videoId: string;
  storyboard: StoryboardManifest;
  limit?: number;
  prefetchImage?: ImagePrefetcher;
}) {
  const resolvedLimit = limit === undefined ? storyboard.sheets.length : Math.max(0, limit);
  const sheets = storyboard.sheets.slice(0, resolvedLimit);
  await Promise.all(
    sheets.map(async (sheet) => {
      if (cache.hasPrefetchedStoryboardSheet(videoId, sheet.url)) {
        return;
      }
      const didPrefetch = await prefetchImage(sheet.url).catch(() => false);
      if (didPrefetch) {
        cache.markStoryboardSheetPrefetched(videoId, sheet.url);
      }
    })
  );
}

export async function preloadInitialPlaybackAssets({
  apiBaseUrl,
  cache,
  videoId,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS,
  prefetchImage = Image.prefetch
}: {
  apiBaseUrl: string;
  cache: PlaybackAssetCache;
  videoId: string;
  fetcher?: FetchLike;
  timeoutMs?: number;
  prefetchImage?: ImagePrefetcher;
}) {
  const [storyboard, interactionPlans] = await Promise.all([
    loadVideoStoryboard({ apiBaseUrl, videoId, fetcher, timeoutMs }),
    loadVideoInteractionPlans({ apiBaseUrl, videoId, fetcher, timeoutMs })
  ]);

  if (storyboard) {
    cache.setStoryboard(videoId, storyboard);
    await prefetchStoryboardSheets({ cache, videoId, storyboard, prefetchImage });
  }
  cache.setInteractionPlans(videoId, interactionPlans);
}

export async function prefetchSeriesCovers({
  series,
  limit = DEFAULT_SERIES_COVER_PREFETCH_LIMIT,
  prefetchImage = Image.prefetch
}: {
  series: PrefetchableSeriesCover[];
  limit?: number;
  prefetchImage?: ImagePrefetcher;
}) {
  const coverUrls = series
    .map((item) => item.coverUrl)
    .filter((url): url is string => typeof url === "string" && url.length > 0)
    .slice(0, Math.max(0, limit));
  await Promise.all(coverUrls.map((url) => prefetchImage(url).catch(() => false)));
}

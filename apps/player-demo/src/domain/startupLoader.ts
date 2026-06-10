import { DEFAULT_API_REQUEST_TIMEOUT_MS, FetchLike, PlayerVideo } from "./playerApi";
import { loadHomeFeedVideos, loadTheaterSeries, PlayerSeriesSummary } from "./playerDataApi";
import type { PlaybackAssetCache } from "./playbackAssetCache";
import { ImagePrefetcher, prefetchSeriesCovers, preloadInitialPlaybackAssets } from "./playbackAssetPreloader";

export interface TheaterSeriesSummary {
  seriesKey: string;
  seriesId?: string;
  title: string;
  summary: string;
  episodeCount: number;
  firstVideoId?: string;
  coverUrl?: string;
}

export interface TheaterSeriesGroup extends TheaterSeriesSummary {
  episodes?: PlayerVideo[];
  coverVideo?: PlayerVideo;
}

export interface StartupData {
  homeVideos: PlayerVideo[];
  theaterSeries: TheaterSeriesGroup[];
}

function toTheaterSeriesSummary(series: PlayerSeriesSummary): TheaterSeriesGroup {
  return {
    seriesKey: series.seriesKey,
    ...(series.seriesId ? { seriesId: series.seriesId } : {}),
    title: series.title,
    summary: series.summary,
    episodeCount: series.episodeCount,
    ...(series.firstVideoId ? { firstVideoId: series.firstVideoId } : {}),
    ...(series.coverUrl ? { coverUrl: series.coverUrl } : {})
  };
}

export async function loadStartupData({
  apiBaseUrl,
  cache,
  fetcher = fetch,
  timeoutMs = DEFAULT_API_REQUEST_TIMEOUT_MS,
  prefetchImage,
  skipPreload = false
}: {
  apiBaseUrl: string;
  cache: PlaybackAssetCache;
  fetcher?: FetchLike;
  timeoutMs?: number;
  prefetchImage?: ImagePrefetcher;
  skipPreload?: boolean;
}): Promise<StartupData> {
  const [homeVideos, theaterSeries] = await Promise.all([
    loadHomeFeedVideos({ apiBaseUrl, fetcher, timeoutMs }),
    loadTheaterSeries({ apiBaseUrl, fetcher, timeoutMs })
  ]);

  const summaries = theaterSeries.map(toTheaterSeriesSummary);
  if (!skipPreload) {
    await Promise.all([
      homeVideos[0]
        ? preloadInitialPlaybackAssets({
            apiBaseUrl,
            cache,
            videoId: homeVideos[0].videoId,
            fetcher,
            timeoutMs,
            ...(prefetchImage ? { prefetchImage } : {})
          })
        : Promise.resolve(),
      prefetchSeriesCovers({
        series: summaries,
        ...(prefetchImage ? { prefetchImage } : {})
      })
    ]);
  }

  return {
    homeVideos,
    theaterSeries: summaries
  };
}

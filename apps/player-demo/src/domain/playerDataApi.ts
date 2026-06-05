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

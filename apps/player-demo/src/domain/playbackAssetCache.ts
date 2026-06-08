import type { StoryboardManifest } from "./storyNavigation";

export interface CachedPlaybackAssets {
  storyboard?: StoryboardManifest;
  interactionPlans?: unknown[];
  prefetchedStoryboardSheets: Set<string>;
}

export interface PlaybackAssetCache {
  get: (videoId: string) => CachedPlaybackAssets | undefined;
  setStoryboard: (videoId: string, storyboard: StoryboardManifest) => void;
  setInteractionPlans: (videoId: string, interactionPlans: unknown[]) => void;
  markStoryboardSheetPrefetched: (videoId: string, url: string) => void;
  hasPrefetchedStoryboardSheet: (videoId: string, url: string) => boolean;
  prune: (activeVideoIds: string[]) => void;
}

function getOrCreateEntry(entries: Map<string, CachedPlaybackAssets>, videoId: string) {
  const existing = entries.get(videoId);
  if (existing) {
    return existing;
  }
  const entry: CachedPlaybackAssets = { prefetchedStoryboardSheets: new Set() };
  entries.set(videoId, entry);
  return entry;
}

export function createPlaybackAssetCache(): PlaybackAssetCache {
  const entries = new Map<string, CachedPlaybackAssets>();
  return {
    get: (videoId) => entries.get(videoId),
    setStoryboard: (videoId, storyboard) => {
      getOrCreateEntry(entries, videoId).storyboard = storyboard;
    },
    setInteractionPlans: (videoId, interactionPlans) => {
      getOrCreateEntry(entries, videoId).interactionPlans = interactionPlans;
    },
    markStoryboardSheetPrefetched: (videoId, url) => {
      getOrCreateEntry(entries, videoId).prefetchedStoryboardSheets.add(url);
    },
    hasPrefetchedStoryboardSheet: (videoId, url) => entries.get(videoId)?.prefetchedStoryboardSheets.has(url) ?? false,
    prune: (activeVideoIds) => {
      const active = new Set(activeVideoIds);
      for (const videoId of entries.keys()) {
        if (!active.has(videoId)) {
          entries.delete(videoId);
        }
      }
    }
  };
}

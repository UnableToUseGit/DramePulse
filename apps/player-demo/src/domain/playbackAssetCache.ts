import type { InteractionAsset } from "./playerDataApi";
import type { StoryChapter } from "./storyNavigation";
import type { StoryboardManifest } from "./storyNavigation";

export interface CachedPlaybackAssets {
  storyboard?: StoryboardManifest;
  storyChapters?: StoryChapter[];
  interactionPlans?: unknown[];
  interactionAssets?: InteractionAsset[];
  prefetchedStoryboardSheets: Set<string>;
}

export interface PlaybackAssetCache {
  get: (videoId: string) => CachedPlaybackAssets | undefined;
  setStoryboard: (videoId: string, storyboard: StoryboardManifest) => void;
  setStoryChapters: (videoId: string, storyChapters: StoryChapter[]) => void;
  setInteractionPlans: (videoId: string, interactionPlans: unknown[]) => void;
  setInteractionAssets: (videoId: string, interactionAssets: InteractionAsset[]) => void;
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
    setStoryChapters: (videoId, storyChapters) => {
      getOrCreateEntry(entries, videoId).storyChapters = storyChapters;
    },
    setInteractionPlans: (videoId, interactionPlans) => {
      getOrCreateEntry(entries, videoId).interactionPlans = interactionPlans;
    },
    setInteractionAssets: (videoId, interactionAssets) => {
      getOrCreateEntry(entries, videoId).interactionAssets = interactionAssets;
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

import type { PlayerFeedItem } from "./playerFeed";
import { getResumePlaybackTime, shouldPreloadFeedPage } from "./playerFeed";

export type FeedPlaybackPageRole = "active" | "preload" | "parked";

export interface FeedPlaybackPageState {
  pageRole: FeedPlaybackPageRole;
  shouldPrepareVideo: boolean;
  shouldOwnPlayback: boolean;
  resumeTime: number;
}

export function getFeedPlaybackPageState({
  item,
  pageIndex,
  activeIndex,
  playbackPositions,
  preloadDistance
}: {
  item: PlayerFeedItem;
  pageIndex: number;
  activeIndex: number;
  playbackPositions: Record<string, number>;
  preloadDistance?: number;
}): FeedPlaybackPageState {
  const isActive = pageIndex === activeIndex;
  const shouldPrepareVideo = shouldPreloadFeedPage({ pageIndex, activeIndex, preloadDistance });
  const pageRole: FeedPlaybackPageRole = isActive ? "active" : shouldPrepareVideo ? "preload" : "parked";
  const savedTime = item.itemType === "video" ? playbackPositions[item.video.videoId] : undefined;
  const duration = item.itemType === "video" ? item.video.duration : 0;

  return {
    pageRole,
    shouldPrepareVideo,
    shouldOwnPlayback: isActive,
    resumeTime: getResumePlaybackTime({ savedTime, duration })
  };
}

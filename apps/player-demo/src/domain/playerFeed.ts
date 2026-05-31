import type { PlayerVideo } from "./playerApi";

export type UserPlaybackIntent = "playing" | "paused";

const RESUME_FROM_START_REMAINING_SEC = 2;

export function getFeedPageIndex({
  offsetY,
  pageHeight,
  itemCount
}: {
  offsetY: number;
  pageHeight: number;
  itemCount: number;
}) {
  if (pageHeight <= 0 || itemCount <= 0) {
    return 0;
  }
  const rawIndex = Math.round(offsetY / pageHeight);
  return Math.min(Math.max(rawIndex, 0), itemCount - 1);
}

export function getVideoPlaybackState({
  isActive,
  userPlaybackIntent
}: {
  isActive: boolean;
  userPlaybackIntent: UserPlaybackIntent;
}) {
  return {
    isStarted: true,
    shouldPlay: isActive && userPlaybackIntent === "playing",
    shouldShowPauseHint: isActive && userPlaybackIntent === "paused"
  };
}

export function getTimelineChromeVisibility({ isTimelineDragging }: { isTimelineDragging: boolean }) {
  return {
    showActionRail: !isTimelineDragging,
    showMeta: !isTimelineDragging,
    showBottomTabs: true
  };
}

export function shouldPreloadFeedPage({
  pageIndex,
  activeIndex,
  preloadDistance = 1
}: {
  pageIndex: number;
  activeIndex: number;
  preloadDistance?: number;
}) {
  return Math.abs(pageIndex - activeIndex) <= preloadDistance;
}

export function getResumePlaybackTime({
  savedTime,
  duration,
  endResetThresholdSec = RESUME_FROM_START_REMAINING_SEC
}: {
  savedTime: number | undefined;
  duration: number;
  endResetThresholdSec?: number;
}) {
  if (savedTime === undefined || !Number.isFinite(savedTime) || savedTime <= 0) {
    return 0;
  }
  if (duration > 0 && duration - savedTime <= endResetThresholdSec) {
    return 0;
  }
  return savedTime;
}

export function getSeriesKey(video: PlayerVideo) {
  if (video.seriesId) {
    return `id:${video.seriesId}`;
  }
  if (video.seriesName) {
    return `name:${video.seriesName}`;
  }
  return undefined;
}

export function findNextEpisodeIndex(videos: PlayerVideo[], currentIndex: number) {
  const currentVideo = videos[currentIndex];
  if (!currentVideo) {
    return undefined;
  }
  const currentSeriesKey = getSeriesKey(currentVideo);
  if (!currentSeriesKey) {
    return undefined;
  }
  const nextIndex = videos.findIndex((video, index) => index > currentIndex && getSeriesKey(video) === currentSeriesKey);
  return nextIndex >= 0 ? nextIndex : undefined;
}

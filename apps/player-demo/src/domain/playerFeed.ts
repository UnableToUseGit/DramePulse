import type { PlayerVideo } from "./playerApi";

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

export function getFeedPlaybackMode({
  hasStartedFeed,
  isActive
}: {
  hasStartedFeed: boolean;
  isActive: boolean;
}) {
  return {
    shouldShowStartEntry: isActive && !hasStartedFeed,
    shouldAutoStart: isActive && hasStartedFeed
  };
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

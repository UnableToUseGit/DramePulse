import type { PlayerVideo } from "./playerApi";

export type UserPlaybackIntent = "playing" | "paused";

export interface SeriesGroup {
  seriesKey: string;
  title: string;
  summary: string;
  episodeCount: number;
  episodes: PlayerVideo[];
  coverVideo: PlayerVideo;
}

const RESUME_FROM_START_REMAINING_SEC = 2;
const EDGE_BACK_SWIPE_WIDTH_PX = 28;
const EDGE_BACK_SWIPE_MIN_DELTA_X_PX = 24;
const EDGE_BACK_SWIPE_BOTTOM_EXCLUSION_PX = 96;
const THEATER_RESTORE_MIN_OFFSET_PX = 24;

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

export function getVideoIndex(videos: PlayerVideo[], videoId: string | undefined) {
  if (!videoId) {
    return 0;
  }
  const index = videos.findIndex((video) => video.videoId === videoId);
  return index >= 0 ? index : 0;
}

export function shouldStartEdgeBackSwipe({
  startX,
  startY,
  screenHeight,
  deltaX,
  deltaY
}: {
  startX: number;
  startY?: number;
  screenHeight?: number;
  deltaX: number;
  deltaY: number;
}) {
  const isInBottomControls =
    startY !== undefined && screenHeight !== undefined && startY >= screenHeight - EDGE_BACK_SWIPE_BOTTOM_EXCLUSION_PX;
  return (
    !isInBottomControls &&
    startX <= EDGE_BACK_SWIPE_WIDTH_PX &&
    deltaX > EDGE_BACK_SWIPE_MIN_DELTA_X_PX &&
    Math.abs(deltaX) > Math.abs(deltaY) * 1.5
  );
}

export function shouldRestoreScrollOffset({ offset, itemCount }: { offset: number; itemCount: number }) {
  return itemCount > 0 && Number.isFinite(offset) && offset > THEATER_RESTORE_MIN_OFFSET_PX;
}

function getEpisodeSortValue(video: PlayerVideo, fallbackIndex: number) {
  return typeof video.episodeNo === "number" ? video.episodeNo : fallbackIndex + 1;
}

export function groupVideosBySeries(videos: PlayerVideo[]): SeriesGroup[] {
  const groups = new Map<string, { firstIndex: number; videos: PlayerVideo[] }>();

  videos.forEach((video, index) => {
    const seriesKey = getSeriesKey(video) ?? `video:${video.videoId}`;
    const group = groups.get(seriesKey);
    if (group) {
      group.videos.push(video);
      return;
    }
    groups.set(seriesKey, { firstIndex: index, videos: [video] });
  });

  return Array.from(groups.entries())
    .sort((a, b) => a[1].firstIndex - b[1].firstIndex)
    .map(([seriesKey, group]) => {
      const episodes = [...group.videos].sort(
        (a, b) => getEpisodeSortValue(a, videos.indexOf(a)) - getEpisodeSortValue(b, videos.indexOf(b))
      );
      const coverVideo = episodes[0];
      const title = coverVideo.seriesName ?? coverVideo.title;
      return {
        seriesKey,
        title,
        summary: coverVideo.plotSummary,
        episodeCount: episodes.length,
        episodes,
        coverVideo
      };
    });
}

export function getSeriesResumeTarget({
  series,
  seriesResumeVideoIds,
  playbackPositions
}: {
  series: SeriesGroup;
  seriesResumeVideoIds: Record<string, string>;
  playbackPositions: Record<string, number>;
}) {
  const resumeVideoId = seriesResumeVideoIds[series.seriesKey];
  const video = series.episodes.find((episode) => episode.videoId === resumeVideoId) ?? series.episodes[0];
  return {
    video,
    time: getResumePlaybackTime({
      savedTime: playbackPositions[video.videoId],
      duration: video.duration
    })
  };
}

import type { PlayerVideo } from "./playerApi";
import type { RoleCommerceFeedAd } from "./roleCommerceAds";

export type UserPlaybackIntent = "playing" | "paused";

export type PlayerFeedVideoItem = {
  itemType: "video";
  itemId: string;
  video: PlayerVideo;
};

export type PlayerFeedRoleCommerceAdItem = {
  itemType: "role_commerce_ad";
  itemId: string;
  ad: RoleCommerceFeedAd;
};

export type PlayerFeedItem = PlayerFeedVideoItem | PlayerFeedRoleCommerceAdItem;

export interface BufferedPlaybackPosition {
  videoId: string;
  time: number;
}


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
const RELEASE_TARGET_VELOCITY_THRESHOLD = 0.8;

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

export function getFeedReleaseTargetIndex({
  offsetY,
  targetOffsetY,
  velocityY,
  pageHeight,
  itemCount,
  activeIndex
}: {
  offsetY: number;
  targetOffsetY?: number;
  velocityY?: number;
  pageHeight: number;
  itemCount: number;
  activeIndex: number;
}) {
  if (pageHeight <= 0 || itemCount <= 0) {
    return activeIndex;
  }
  if (targetOffsetY === undefined && velocityY !== undefined && Math.abs(velocityY) >= RELEASE_TARGET_VELOCITY_THRESHOLD) {
    return Math.min(Math.max(activeIndex + Math.sign(velocityY), 0), itemCount - 1);
  }
  const resolvedOffsetY =
    targetOffsetY !== undefined && Number.isFinite(targetOffsetY) ? targetOffsetY : offsetY;
  return getFeedPageIndex({
    offsetY: resolvedOffsetY,
    pageHeight,
    itemCount
  });
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

export function getFeedScrollEnabled({ isTimelineDragging }: { isTimelineDragging: boolean }) {
  return !isTimelineDragging;
}

export function stagePlaybackPositionUpdate({
  isFeedDragging,
  playbackPositions,
  videoId,
  time
}: {
  isFeedDragging: boolean;
  playbackPositions: Record<string, number>;
  videoId: string;
  time: number;
}) {
  if (playbackPositions[videoId] === time) {
    return {
      bufferedPosition: undefined,
      nextPlaybackPositions: playbackPositions,
      shouldPublish: false
    };
  }
  if (isFeedDragging) {
    return {
      bufferedPosition: { videoId, time },
      nextPlaybackPositions: playbackPositions,
      shouldPublish: false
    };
  }
  return {
    bufferedPosition: undefined,
    nextPlaybackPositions: {
      ...playbackPositions,
      [videoId]: time
    },
    shouldPublish: true
  };
}

export function flushBufferedPlaybackPosition({
  bufferedPosition,
  playbackPositions
}: {
  bufferedPosition: BufferedPlaybackPosition | undefined;
  playbackPositions: Record<string, number>;
}) {
  if (!bufferedPosition || playbackPositions[bufferedPosition.videoId] === bufferedPosition.time) {
    return {
      bufferedPosition: undefined,
      nextPlaybackPositions: playbackPositions,
      shouldPublish: false
    };
  }
  return {
    bufferedPosition: undefined,
    nextPlaybackPositions: {
      ...playbackPositions,
      [bufferedPosition.videoId]: bufferedPosition.time
    },
    shouldPublish: true
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

function shouldPlaceRoleCommerceAdAfterVideo({
  ad,
  video,
  videoIndex
}: {
  ad: RoleCommerceFeedAd;
  video: PlayerVideo;
  videoIndex: number;
}) {
  if (ad.placement === "after_first_video") {
    return videoIndex === 0;
  }
  return ad.afterVideoId === video.videoId;
}

export function buildPlayerFeedItems({
  videos,
  roleCommerceAds = [],
  mode
}: {
  videos: PlayerVideo[];
  roleCommerceAds?: RoleCommerceFeedAd[];
  mode: "home" | "series";
}): PlayerFeedItem[] {
  return videos.flatMap((video, videoIndex) => {
    const videoItem: PlayerFeedVideoItem = {
      itemType: "video",
      itemId: `video:${video.videoId}`,
      video
    };
    if (mode !== "series") {
      return [videoItem];
    }
    const adItems: PlayerFeedRoleCommerceAdItem[] = roleCommerceAds
      .filter((ad) => shouldPlaceRoleCommerceAdAfterVideo({ ad, video, videoIndex }))
      .map((ad) => ({
        itemType: "role_commerce_ad",
        itemId: `role-commerce:${ad.adId}`,
        ad
      }));
    return [videoItem, ...adItems];
  });
}

export function findNextFeedItemIndex(items: PlayerFeedItem[], currentIndex: number) {
  const nextIndex = currentIndex + 1;
  return nextIndex >= 0 && nextIndex < items.length ? nextIndex : undefined;
}

export function getVideoIndexFromFeedItems(items: PlayerFeedItem[], videoId: string | undefined) {
  if (!videoId) {
    return 0;
  }
  const index = items.findIndex((item) => item.itemType === "video" && item.video.videoId === videoId);
  return index >= 0 ? index : 0;
}

export function getRequestedVideoFeedIndex({
  items,
  previousRequestedVideoId,
  requestedVideoId,
  activeIndex
}: {
  items: PlayerFeedItem[];
  previousRequestedVideoId: string | undefined;
  requestedVideoId: string | undefined;
  activeIndex: number;
}) {
  if (!requestedVideoId || requestedVideoId === previousRequestedVideoId) {
    return undefined;
  }
  const index = items.findIndex((item) => item.itemType === "video" && item.video.videoId === requestedVideoId);
  return index >= 0 && index !== activeIndex ? index : undefined;
}

export function getNextEpisodeInfoByIndex(videos: PlayerVideo[]) {
  return videos.map((video, index) => {
    const nextIndex = findNextEpisodeIndex(videos, index);
    const nextEpisode = nextIndex !== undefined ? videos[nextIndex] : undefined;
    return {
      hasNextEpisode: nextEpisode !== undefined,
      nextEpisodeLabel: nextEpisode?.episodeLabel
    };
  });
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

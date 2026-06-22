import type { BufferOptions, VideoSource } from "expo-video";
import type { FeedPlaybackPageRole } from "./feedPlaybackCoordinator";

export const FEED_VIDEO_PRELOAD_BUFFER_OPTIONS: BufferOptions = {
  maxBufferBytes: 24 * 1024 * 1024,
  minBufferForPlayback: 1,
  preferredForwardBufferDuration: 8,
  prioritizeTimeOverSizeThreshold: true,
  waitsToMinimizeStalling: false
};

export const FEED_VIDEO_ACTIVE_BUFFER_OPTIONS: BufferOptions = {
  maxBufferBytes: 48 * 1024 * 1024,
  minBufferForPlayback: 2.5,
  preferredForwardBufferDuration: 18,
  prioritizeTimeOverSizeThreshold: true,
  waitsToMinimizeStalling: true
};

export const FEED_VIDEO_BUFFER_OPTIONS = FEED_VIDEO_ACTIVE_BUFFER_OPTIONS;
export const FEED_VIDEO_SOURCE_CACHING_ENABLED = false;

export function getFeedVideoBufferOptions(pageRole: FeedPlaybackPageRole): BufferOptions {
  if (pageRole === "active") {
    return FEED_VIDEO_ACTIVE_BUFFER_OPTIONS;
  }
  return FEED_VIDEO_PRELOAD_BUFFER_OPTIONS;
}

export function buildVideoStageSource({
  enableCaching,
  streamUrl
}: {
  enableCaching: boolean;
  streamUrl: string | number;
}): VideoSource {
  if (typeof streamUrl !== "string" || !enableCaching) {
    return streamUrl;
  }
  return {
    uri: streamUrl,
    useCaching: true,
    contentType: "progressive"
  };
}

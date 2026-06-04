import type { BufferOptions, VideoSource } from "expo-video";

export const FEED_VIDEO_BUFFER_OPTIONS: BufferOptions = {
  maxBufferBytes: 24 * 1024 * 1024,
  minBufferForPlayback: 1,
  preferredForwardBufferDuration: 8,
  prioritizeTimeOverSizeThreshold: true,
  waitsToMinimizeStalling: false
};

export const FEED_VIDEO_SOURCE_CACHING_ENABLED = false;

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

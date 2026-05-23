import { buildApiUrl } from "../config/api";

export interface ApiVideo {
  video_id: string;
  title: string;
  episode_no?: number | null;
  duration?: number | null;
  stream_url: string;
  source: string;
}

interface VideoListResponse {
  videos: ApiVideo[];
}

export async function fetchFirstVideoStreamUrl(): Promise<string> {
  const response = await fetch(buildApiUrl("/api/videos"));
  if (!response.ok) {
    throw new Error(`Failed to fetch videos: ${response.status}`);
  }
  const payload = (await response.json()) as VideoListResponse;
  const firstVideo = payload.videos[0];
  if (!firstVideo) {
    throw new Error("No videos returned from API");
  }
  return buildApiUrl(firstVideo.stream_url);
}

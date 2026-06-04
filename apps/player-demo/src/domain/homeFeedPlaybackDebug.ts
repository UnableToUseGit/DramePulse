import type { HomeFeedPlaybackEvent, HomeFeedPlaybackPageSnapshot } from "./homeFeedPlaybackObserver";

function formatPlayerStatus(status: string | undefined) {
  if (status === "readyToPlay") {
    return "ready";
  }
  return status ?? "no-player";
}

export function formatHomeFeedPlaybackLatency(latencyMs: number | undefined) {
  return latencyMs === undefined ? "—" : `${latencyMs} ms`;
}

export function formatHomeFeedPlaybackPage(page: HomeFeedPlaybackPageSnapshot) {
  const playing = page.isPlaying === undefined ? "play?" : page.isPlaying ? "playing" : "paused";
  const muted = page.isMuted === undefined ? "mute?" : page.isMuted ? "muted" : "audible";
  const role = page.hasPlaybackOwnership ? "owner" : page.isPreloaded ? "preload" : "idle";
  return `${String(page.pageIndex).padStart(2, "0")} ${page.videoId} · ${formatPlayerStatus(
    page.playerStatus
  )} · ${playing} · ${muted} · ${role}`;
}

export function formatHomeFeedPlaybackEvent(event: HomeFeedPlaybackEvent) {
  const detail = event.details
    ? Object.entries(event.details)
        .filter(([, value]) => value !== undefined)
        .map(([key, value]) => `${key}=${String(value)}`)
        .join(" ")
    : "";
  return `+${String(event.elapsedMs).padStart(4, "0")} #${event.sequence} ${event.eventType}${
    event.videoId ? ` ${event.videoId}` : ""
  }${detail ? ` ${detail}` : ""}`;
}

import type { PlayerVideo } from "./playerApi";
import { getSeriesKey } from "./playerFeed";

export interface SeriesSummary {
  id: string;
  title: string;
  plotSummary: string;
  episodes: PlayerVideo[];
  totalDuration: number;
}

function getEpisodeOrder(video: PlayerVideo) {
  return video.episodeNo ?? Number(video.episodeLabel?.match(/\d+/)?.[0] ?? 0);
}

function getFallbackSeriesId(video: PlayerVideo) {
  return getSeriesKey(video) ?? `video:${video.videoId}`;
}

export function buildSeriesCatalog(videos: PlayerVideo[]): SeriesSummary[] {
  const seriesById = new Map<string, SeriesSummary>();

  videos.forEach((video) => {
    const id = getFallbackSeriesId(video);
    const current = seriesById.get(id);
    if (current) {
      current.episodes.push(video);
      current.totalDuration += video.duration;
      if (!current.plotSummary || current.plotSummary === current.title) {
        current.plotSummary = video.plotSummary;
      }
      return;
    }

    seriesById.set(id, {
      id,
      title: video.seriesName || video.title,
      plotSummary: video.plotSummary,
      episodes: [video],
      totalDuration: video.duration
    });
  });

  return Array.from(seriesById.values())
    .map((series) => ({
      ...series,
      episodes: [...series.episodes].sort((left, right) => getEpisodeOrder(left) - getEpisodeOrder(right))
    }))
    .sort((left, right) => left.title.localeCompare(right.title, "zh-Hans-CN"));
}

export function findSeriesForVideo(videos: PlayerVideo[], selectedVideo: PlayerVideo) {
  const selectedSeriesKey = getFallbackSeriesId(selectedVideo);
  return buildSeriesCatalog(videos).find((series) => series.id === selectedSeriesKey);
}

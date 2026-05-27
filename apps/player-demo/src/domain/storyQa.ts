import type { PlayerVideo } from "./playerApi";

export interface StoryQaSource {
  score: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface StoryQaAnswer {
  answer: string;
  sources: StoryQaSource[];
}

export interface StoryQaFetchLike {
  (
    input: string,
    init?: {
      method?: string;
      headers?: Record<string, string>;
      body?: string;
    }
  ): Promise<{
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
  }>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function joinUrl(baseUrl: string, path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

function normalizeSources(value: unknown): StoryQaSource[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord).map((source) => ({
    score: typeof source.score === "number" ? source.score : 0,
    text: typeof source.text === "string" ? source.text : "",
    metadata: isRecord(source.metadata) ? source.metadata : {}
  }));
}

export function resolveStoryQaContext(video: PlayerVideo): { seriesId: string; currentEpisode: number } {
  const labelEpisode = video.episodeLabel?.match(/\d+/)?.[0];
  return {
    seriesId: video.seriesId || video.videoId,
    currentEpisode: video.episodeNo ?? (labelEpisode ? Number(labelEpisode) : 1)
  };
}

export async function askStoryQa({
  apiBaseUrl,
  question,
  seriesId,
  currentEpisode,
  currentTime,
  fetcher = fetch
}: {
  apiBaseUrl: string;
  question: string;
  seriesId: string;
  currentEpisode: number;
  currentTime: number;
  fetcher?: StoryQaFetchLike;
}): Promise<StoryQaAnswer> {
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion) {
    throw new Error("请输入问题");
  }

  const response = await fetcher(joinUrl(apiBaseUrl, "/api/story-qa/ask"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      question: trimmedQuestion,
      series_id: seriesId,
      current_episode: currentEpisode,
      current_time: Math.max(0, currentTime)
    })
  });
  const payload = await response.json();

  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : undefined;
    throw new Error(detail || `剧情问答请求失败 (${response.status})`);
  }
  if (!isRecord(payload) || typeof payload.answer !== "string" || !payload.answer.trim()) {
    throw new Error("暂时没有可展示的回答");
  }

  return {
    answer: payload.answer,
    sources: normalizeSources(payload.sources)
  };
}

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
    text?: () => Promise<string>;
    body?: ReadableStream<Uint8Array> | null;
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

export async function askStoryQaStream({
  apiBaseUrl,
  question,
  seriesId,
  currentEpisode,
  currentTime,
  onDelta,
  fetcher = fetch
}: {
  apiBaseUrl: string;
  question: string;
  seriesId: string;
  currentEpisode: number;
  currentTime: number;
  onDelta: (text: string) => void;
  fetcher?: StoryQaFetchLike;
}): Promise<string> {
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion) {
    throw new Error("请输入问题");
  }

  const response = await fetcher(joinUrl(apiBaseUrl, "/api/story-qa/ask-stream"), {
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

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = await response.json();
      detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : undefined;
    } catch {
      detail = undefined;
    }
    throw new Error(detail || `鍓ф儏闂瓟璇锋眰澶辫触 (${response.status})`);
  }

  let answer = "";
  if (response.body?.getReader) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      const delta = decoder.decode(value, { stream: true });
      if (delta) {
        answer += delta;
        onDelta(delta);
      }
    }
    const tail = decoder.decode();
    if (tail) {
      answer += tail;
      onDelta(tail);
    }
  } else if (response.text) {
    answer = await response.text();
    if (answer) {
      onDelta(answer);
    }
  }

  if (!answer.trim()) {
    throw new Error("鏆傛椂娌℃湁鍙睍绀虹殑鍥炵瓟");
  }
  return answer;
}

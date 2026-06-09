export type WatchAssistantActionType = "answer" | "seek" | "next_episode" | "pause" | "resume" | "noop";

export interface WatchAssistantAction {
  type: WatchAssistantActionType;
  targetTime?: number;
  relativeSeconds?: number;
  reason?: string;
}

export interface WatchAssistantToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  status: "ok" | "error";
  result: Record<string, unknown>;
  error?: string;
}

export interface WatchAssistantResponse {
  reply: string;
  actions: WatchAssistantAction[];
  toolCalls: WatchAssistantToolCall[];
  sources: Array<{ score: number; text: string; metadata: Record<string, unknown> }>;
}

export interface WatchAssistantTranscription {
  text: string;
  confidence: number;
  language: string;
  durationMs: number;
}

export interface WatchAssistantFetchLike {
  (
    input: string,
    init?: {
      method?: string;
      headers?: Record<string, string>;
      body?: string | FormData;
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

function normalizeAction(value: unknown): WatchAssistantAction | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const type = value.type;
  if (!["answer", "seek", "next_episode", "pause", "resume", "noop"].includes(String(type))) {
    return undefined;
  }
  const action: WatchAssistantAction = { type: type as WatchAssistantActionType };
  if (typeof value.target_time === "number") {
    action.targetTime = value.target_time;
  }
  if (typeof value.relative_seconds === "number") {
    action.relativeSeconds = value.relative_seconds;
  }
  if (typeof value.reason === "string") {
    action.reason = value.reason;
  }
  return action;
}

function normalizeToolCall(value: unknown): WatchAssistantToolCall | undefined {
  if (!isRecord(value) || typeof value.tool !== "string") {
    return undefined;
  }
  return {
    tool: value.tool,
    arguments: isRecord(value.arguments) ? value.arguments : {},
    status: value.status === "error" ? "error" : "ok",
    result: isRecord(value.result) ? value.result : {},
    error: typeof value.error === "string" ? value.error : undefined
  };
}

function normalizeSources(value: unknown): WatchAssistantResponse["sources"] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord).map((source) => ({
    score: typeof source.score === "number" ? source.score : 0,
    text: typeof source.text === "string" ? source.text : "",
    metadata: isRecord(source.metadata) ? source.metadata : {}
  }));
}

function normalizeTranscription(value: unknown): WatchAssistantTranscription {
  if (!isRecord(value) || typeof value.text !== "string") {
    throw new Error("语音转写返回格式不可用");
  }
  const text = value.text.trim();
  if (!text) {
    throw new Error("没有听清，可以再说一次");
  }
  return {
    text,
    confidence: typeof value.confidence === "number" ? value.confidence : 0,
    language: typeof value.language === "string" ? value.language : "zh",
    durationMs: typeof value.duration_ms === "number" ? value.duration_ms : 0
  };
}

export async function transcribeWatchAssistantAudio({
  apiBaseUrl,
  audioUri,
  seriesId,
  videoId,
  currentEpisode,
  currentTime,
  duration,
  fetcher = fetch
}: {
  apiBaseUrl: string;
  audioUri: string;
  seriesId: string;
  videoId: string;
  currentEpisode: number;
  currentTime: number;
  duration: number;
  fetcher?: WatchAssistantFetchLike;
}): Promise<WatchAssistantTranscription> {
  if (!audioUri) {
    throw new Error("没有可上传的录音");
  }
  const formData = new FormData();
  formData.append("audio", {
    uri: audioUri,
    name: "watch-assistant.m4a",
    type: "audio/mp4"
  } as unknown as Blob);
  formData.append("series_id", seriesId);
  formData.append("video_id", videoId);
  formData.append("current_episode", String(currentEpisode));
  formData.append("current_time", String(Math.max(0, currentTime)));
  formData.append("duration", String(Math.max(0, duration)));

  const response = await fetcher(joinUrl(apiBaseUrl, "/api/watch-assistant/transcribe"), {
    method: "POST",
    body: formData
  });
  const payload = await response.json();
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : undefined;
    throw new Error(detail || `语音转写失败 (${response.status})`);
  }
  return normalizeTranscription(payload);
}

export async function askWatchAssistant({
  apiBaseUrl,
  message,
  seriesId,
  videoId,
  currentEpisode,
  currentTime,
  duration,
  availableTools = ["story_qa", "seek", "seek_relative", "next_episode", "pause", "resume"],
  fetcher = fetch
}: {
  apiBaseUrl: string;
  message: string;
  seriesId: string;
  videoId: string;
  currentEpisode: number;
  currentTime: number;
  duration: number;
  availableTools?: string[];
  fetcher?: WatchAssistantFetchLike;
}): Promise<WatchAssistantResponse> {
  const trimmedMessage = message.trim();
  if (!trimmedMessage) {
    throw new Error("请输入指令或剧情问题");
  }

  const response = await fetcher(joinUrl(apiBaseUrl, "/api/watch-assistant/act"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: trimmedMessage,
      series_id: seriesId,
      video_id: videoId,
      current_episode: currentEpisode,
      current_time: Math.max(0, currentTime),
      duration: Math.max(0, duration),
      available_tools: availableTools
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : undefined;
    throw new Error(detail || `观看助手请求失败 (${response.status})`);
  }
  if (!isRecord(payload) || typeof payload.reply !== "string") {
    throw new Error("观看助手返回格式不可用");
  }
  return {
    reply: payload.reply,
    actions: Array.isArray(payload.actions) ? (payload.actions.map(normalizeAction).filter(Boolean) as WatchAssistantAction[]) : [],
    toolCalls: Array.isArray(payload.tool_calls)
      ? (payload.tool_calls.map(normalizeToolCall).filter(Boolean) as WatchAssistantToolCall[])
      : [],
    sources: normalizeSources(payload.sources)
  };
}

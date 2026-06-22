type HomeFeedPlaybackLogFetcher = (
  url: string,
  init: {
    body: string;
    headers: Record<string, string>;
    method: "POST";
  }
) => Promise<unknown>;

declare const fetch: HomeFeedPlaybackLogFetcher | undefined;

const DEFAULT_FLUSH_DELAY_MS = 500;

function resolveEndpoint(apiBaseUrl: string) {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/dev/home-feed-playback-logs`;
}

export function createHomeFeedPlaybackFileLogger({
  apiBaseUrl,
  fallbackLog = (line) => console.log(line),
  fetcher = fetch,
  flushDelayMs = DEFAULT_FLUSH_DELAY_MS
}: {
  apiBaseUrl: string;
  fallbackLog?: (line: string) => void;
  fetcher?: HomeFeedPlaybackLogFetcher;
  flushDelayMs?: number;
}) {
  const endpoint = resolveEndpoint(apiBaseUrl);
  let pendingFlush: ReturnType<typeof setTimeout> | undefined;
  let queue: string[] = [];

  const flush = () => {
    pendingFlush = undefined;
    if (!fetcher || queue.length === 0) {
      queue = [];
      return;
    }
    const lines = queue;
    queue = [];
    fetcher(endpoint, {
      body: JSON.stringify({ lines }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    }).catch(() => {
      // Dev file logging is best-effort; terminal logging remains the source of truth.
    });
  };

  return (line: string) => {
    fallbackLog(line);
    queue.push(line);
    if (pendingFlush === undefined) {
      pendingFlush = setTimeout(flush, flushDelayMs);
    }
  };
}

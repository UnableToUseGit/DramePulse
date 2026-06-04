export type HomeFeedPlaybackEventType =
  | "feed_scroll_begin"
  | "feed_scroll_release"
  | "feed_scroll_end"
  | "feed_active_item_change"
  | "feed_playback_owner_change"
  | "page_mount"
  | "page_unmount"
  | "preload_state_change"
  | "playback_ownership_change"
  | "player_create"
  | "player_release"
  | "status_change"
  | "source_load"
  | "resume_position_initialized"
  | "seek_requested"
  | "seek_applied"
  | "play_command"
  | "pause_command"
  | "buffer_health"
  | "playing_change"
  | "muted_change"
  | "first_frame_render";

export type HomeFeedPlaybackEventDetails = Record<string, string | number | boolean | undefined>;

export interface HomeFeedPlaybackEventInput {
  eventType: HomeFeedPlaybackEventType;
  videoId?: string;
  pageIndex?: number;
  activeIndex?: number;
  details?: HomeFeedPlaybackEventDetails;
}

export interface HomeFeedPlaybackEvent extends HomeFeedPlaybackEventInput {
  sequence: number;
  timestampMs: number;
  elapsedMs: number;
}

export interface HomeFeedPlaybackPageSnapshot {
  videoId: string;
  pageIndex: number;
  isMounted: boolean;
  isPreloaded: boolean;
  hasPlaybackOwnership: boolean;
  playerStatus?: string;
  isPlaying?: boolean;
  isMuted?: boolean;
}

export interface HomeFeedPlaybackSwitchMetrics {
  videoId: string;
  pageIndex: number;
  activeChangedAtMs: number;
  playingLatencyMs?: number;
  firstFrameLatencyMs?: number;
}

export interface HomeFeedPlaybackSnapshot {
  events: HomeFeedPlaybackEvent[];
  pages: HomeFeedPlaybackPageSnapshot[];
  activeIndex: number | undefined;
  activeVideoId: string | undefined;
  switchMetrics: HomeFeedPlaybackSwitchMetrics | undefined;
}

export interface HomeFeedPlaybackObserver {
  record: (event: HomeFeedPlaybackEventInput) => void;
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => HomeFeedPlaybackSnapshot;
  clear: () => void;
}

const DEFAULT_MAX_EVENTS = 200;
const STATE_EVENT_TYPES = new Set<HomeFeedPlaybackEventType>([
  "preload_state_change",
  "playback_ownership_change",
  "status_change",
  "playing_change",
  "muted_change"
]);

function getPageKey(videoId: string, pageIndex: number) {
  return `${pageIndex}:${videoId}`;
}

function isSameStateEvent(previous: HomeFeedPlaybackEvent | undefined, next: HomeFeedPlaybackEventInput) {
  return (
    previous !== undefined &&
    STATE_EVENT_TYPES.has(next.eventType) &&
    previous.eventType === next.eventType &&
    previous.videoId === next.videoId &&
    previous.pageIndex === next.pageIndex &&
    JSON.stringify(previous.details) === JSON.stringify(next.details)
  );
}

function createInitialSnapshot(): HomeFeedPlaybackSnapshot {
  return {
    events: [],
    pages: [],
    activeIndex: undefined,
    activeVideoId: undefined,
    switchMetrics: undefined
  };
}

export function createHomeFeedPlaybackObserver({
  maxEvents = DEFAULT_MAX_EVENTS,
  now = Date.now,
  log = (line) => console.log(line)
}: {
  maxEvents?: number;
  now?: () => number;
  log?: (line: string) => void;
} = {}): HomeFeedPlaybackObserver {
  const startedAtMs = now();
  const pages = new Map<string, HomeFeedPlaybackPageSnapshot>();
  const listeners = new Set<() => void>();
  let sequence = 0;
  let snapshot = createInitialSnapshot();

  const publishSnapshot = ({
    events = snapshot.events,
    activeIndex = snapshot.activeIndex,
    activeVideoId = snapshot.activeVideoId,
    switchMetrics = snapshot.switchMetrics
  }: Partial<HomeFeedPlaybackSnapshot> = {}) => {
    snapshot = {
      events,
      pages: [...pages.values()].sort((left, right) => left.pageIndex - right.pageIndex),
      activeIndex,
      activeVideoId,
      switchMetrics
    };
    listeners.forEach((listener) => {
      try {
        listener();
      } catch {
        // Observability must never interrupt playback.
      }
    });
  };

  const updatePage = (
    event: HomeFeedPlaybackEventInput,
    update: (page: HomeFeedPlaybackPageSnapshot) => HomeFeedPlaybackPageSnapshot
  ) => {
    if (event.videoId === undefined || event.pageIndex === undefined) {
      return;
    }
    const key = getPageKey(event.videoId, event.pageIndex);
    const page = pages.get(key) ?? {
      videoId: event.videoId,
      pageIndex: event.pageIndex,
      isMounted: false,
      isPreloaded: false,
      hasPlaybackOwnership: false
    };
    pages.set(key, update(page));
  };

  const record = (input: HomeFeedPlaybackEventInput) => {
    if (isSameStateEvent(snapshot.events[snapshot.events.length - 1], input)) {
      return;
    }

    const timestampMs = now();
    const event: HomeFeedPlaybackEvent = {
      ...input,
      sequence: ++sequence,
      timestampMs,
      elapsedMs: timestampMs - startedAtMs
    };
    const events = [...snapshot.events, event].slice(-Math.max(1, maxEvents));
    let activeIndex = snapshot.activeIndex;
    let activeVideoId = snapshot.activeVideoId;
    let switchMetrics = snapshot.switchMetrics;

    if (
      (input.eventType === "feed_active_item_change" || input.eventType === "feed_playback_owner_change") &&
      input.videoId !== undefined &&
      input.pageIndex !== undefined
    ) {
      if (input.eventType === "feed_active_item_change") {
        activeIndex = input.activeIndex ?? input.pageIndex;
        activeVideoId = input.videoId;
      }
      switchMetrics = {
        videoId: input.videoId,
        pageIndex: input.pageIndex,
        activeChangedAtMs: timestampMs
      };
    }

    if (
      switchMetrics &&
      input.videoId === switchMetrics.videoId &&
      input.pageIndex === switchMetrics.pageIndex &&
      input.eventType === "playing_change" &&
      input.details?.isPlaying === true &&
      switchMetrics.playingLatencyMs === undefined
    ) {
      switchMetrics = {
        ...switchMetrics,
        playingLatencyMs: timestampMs - switchMetrics.activeChangedAtMs
      };
    }

    if (
      switchMetrics &&
      input.videoId === switchMetrics.videoId &&
      input.pageIndex === switchMetrics.pageIndex &&
      input.eventType === "first_frame_render" &&
      switchMetrics.firstFrameLatencyMs === undefined
    ) {
      switchMetrics = {
        ...switchMetrics,
        firstFrameLatencyMs: timestampMs - switchMetrics.activeChangedAtMs
      };
    }

    if (input.eventType === "page_mount") {
      updatePage(input, (page) => ({ ...page, isMounted: true }));
    } else if (input.eventType === "page_unmount") {
      updatePage(input, (page) => ({ ...page, isMounted: false }));
    } else if (input.eventType === "preload_state_change") {
      updatePage(input, (page) => ({ ...page, isPreloaded: input.details?.isPreloaded === true }));
    } else if (input.eventType === "playback_ownership_change") {
      updatePage(input, (page) => ({ ...page, hasPlaybackOwnership: input.details?.hasPlaybackOwnership === true }));
    } else if (input.eventType === "player_create") {
      updatePage(input, (page) => ({ ...page, playerStatus: "idle", isPlaying: false }));
    } else if (input.eventType === "player_release") {
      updatePage(input, (page) => ({
        ...page,
        playerStatus: undefined,
        isPlaying: false,
        isMuted: undefined
      }));
    } else if (input.eventType === "status_change") {
      updatePage(input, (page) => ({ ...page, playerStatus: String(input.details?.status ?? "unknown") }));
    } else if (input.eventType === "playing_change") {
      updatePage(input, (page) => ({ ...page, isPlaying: input.details?.isPlaying === true }));
    } else if (input.eventType === "muted_change") {
      updatePage(input, (page) => ({ ...page, isMuted: input.details?.isMuted === true }));
    }

    publishSnapshot({ events, activeIndex, activeVideoId, switchMetrics });
    try {
      log(`[HomeFeedPlayback] ${JSON.stringify(event)}`);
    } catch {
      // Logging is best-effort and must not affect playback.
    }
  };

  return {
    record,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSnapshot() {
      return snapshot;
    },
    clear() {
      pages.clear();
      snapshot = createInitialSnapshot();
      publishSnapshot();
    }
  };
}

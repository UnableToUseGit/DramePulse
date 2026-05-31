export interface StoryChapter {
  chapterId: string;
  videoId?: string;
  startTime: number;
  endTime: number;
  title: string;
  summary?: string;
  importance?: number;
}

export interface StoryboardSheet {
  url: string;
  startTime: number;
  frameCount: number;
}

export interface StoryboardManifest {
  videoId: string;
  intervalSeconds: number;
  frameWidth: number;
  frameHeight: number;
  columns: number;
  rows: number;
  sheets: StoryboardSheet[];
}

export interface ChapterTick {
  chapterId: string;
  percent: number;
}

export interface StoryboardCell {
  sheetUrl: string;
  frameWidth: number;
  frameHeight: number;
  sheetWidth: number;
  sheetHeight: number;
  offsetX: number;
  offsetY: number;
}

export interface TimelinePresentation {
  trackHeight: number;
  trackBorderRadius: number;
  thumbWidth: number;
  thumbHeight: number;
  thumbTop: number;
  thumbMarginLeft: number;
  thumbBorderRadius: number;
  tickTop: number;
  tickHeight: number;
  tickOpacity: number;
}

const DEFAULT_TIMELINE_PRESENTATION: TimelinePresentation = {
  trackHeight: 3,
  trackBorderRadius: 2,
  thumbWidth: 11,
  thumbHeight: 11,
  thumbTop: -4,
  thumbMarginLeft: -5.5,
  thumbBorderRadius: 6,
  tickTop: -1,
  tickHeight: 5,
  tickOpacity: 0.82
};

const DRAGGING_TIMELINE_PRESENTATION: TimelinePresentation = {
  trackHeight: 14,
  trackBorderRadius: 7,
  thumbWidth: 7,
  thumbHeight: 28,
  thumbTop: -7,
  thumbMarginLeft: -3.5,
  thumbBorderRadius: 4,
  tickTop: 3,
  tickHeight: 8,
  tickOpacity: 0.35
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toNumber(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function toString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function negativeOffset(value: number) {
  return value === 0 ? 0 : -value;
}

export function getStoryChapterAtTime(chapters: StoryChapter[] | undefined, time: number): StoryChapter | undefined {
  if (!chapters || chapters.length === 0) {
    return undefined;
  }
  const sorted = [...chapters].sort((a, b) => a.startTime - b.startTime);
  const exact = sorted.find((chapter) => chapter.startTime <= time && time < chapter.endTime);
  if (exact) {
    return exact;
  }
  const last = sorted[sorted.length - 1];
  if (last && time >= last.endTime) {
    return last;
  }
  return undefined;
}

export function getChapterTicks(chapters: StoryChapter[] | undefined, duration: number): ChapterTick[] {
  if (!chapters || chapters.length === 0 || duration <= 0) {
    return [];
  }
  return chapters
    .filter((chapter) => chapter.startTime > 0 && chapter.startTime < duration)
    .map((chapter) => ({
      chapterId: chapter.chapterId,
      percent: clamp((chapter.startTime / duration) * 100, 0, 100)
    }));
}

export function getTimelinePresentation(isDragging: boolean): TimelinePresentation {
  return isDragging ? DRAGGING_TIMELINE_PRESENTATION : DEFAULT_TIMELINE_PRESENTATION;
}

export function getTimelineTimeFromPageX({
  pageX,
  trackPageX,
  trackWidth,
  duration
}: {
  pageX: number;
  trackPageX: number;
  trackWidth: number;
  duration: number;
}) {
  if (trackWidth <= 0 || duration <= 0) {
    return 0;
  }
  const ratio = clamp((pageX - trackPageX) / trackWidth, 0, 1);
  return ratio * duration;
}

export function normalizeStoryChapters(value: unknown): StoryChapter[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter(isRecord)
    .map((item) => {
      const chapterId = toString(item.chapter_id) ?? toString(item.chapterId);
      const videoId = toString(item.video_id) ?? toString(item.videoId);
      const startTime = toNumber(item.start_time ?? item.startTime);
      const endTime = toNumber(item.end_time ?? item.endTime);
      const title = toString(item.title);
      if (!chapterId || startTime === undefined || endTime === undefined || endTime <= startTime || !title) {
        return undefined;
      }
      const summary = toString(item.summary);
      const importance = toNumber(item.importance);
      return {
        chapterId,
        ...(videoId ? { videoId } : {}),
        startTime,
        endTime,
        title,
        ...(summary ? { summary } : {}),
        ...(importance !== undefined ? { importance } : {})
      };
    })
    .filter((chapter): chapter is StoryChapter => chapter !== undefined)
    .sort((a, b) => a.startTime - b.startTime);
}

export function normalizeStoryboardManifest(value: unknown): StoryboardManifest | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const videoId = toString(value.video_id) ?? toString(value.videoId);
  const intervalSeconds = toNumber(value.interval_seconds ?? value.intervalSeconds);
  const frameWidth = toNumber(value.frame_width ?? value.frameWidth);
  const frameHeight = toNumber(value.frame_height ?? value.frameHeight);
  const columns = toNumber(value.columns);
  const rows = toNumber(value.rows);
  const rawSheets = Array.isArray(value.sheets) ? value.sheets : [];
  if (!videoId || !intervalSeconds || !frameWidth || !frameHeight || !columns || !rows) {
    return undefined;
  }
  const sheets = rawSheets
    .filter(isRecord)
    .map((sheet) => {
      const url = toString(sheet.url);
      const startTime = toNumber(sheet.start_time ?? sheet.startTime);
      const frameCount = toNumber(sheet.frame_count ?? sheet.frameCount);
      if (!url || startTime === undefined || frameCount === undefined || frameCount <= 0) {
        return undefined;
      }
      return { url, startTime, frameCount };
    })
    .filter((sheet): sheet is StoryboardSheet => sheet !== undefined)
    .sort((a, b) => a.startTime - b.startTime);
  if (sheets.length === 0) {
    return undefined;
  }
  return {
    videoId,
    intervalSeconds,
    frameWidth,
    frameHeight,
    columns,
    rows,
    sheets
  };
}

export function getStoryboardCell(
  storyboard: StoryboardManifest | undefined,
  time: number
): StoryboardCell | undefined {
  if (!storyboard || storyboard.intervalSeconds <= 0 || storyboard.columns <= 0 || storyboard.rows <= 0) {
    return undefined;
  }
  const frameIndex = Math.max(0, Math.floor(time / storyboard.intervalSeconds));
  const cellsPerSheet = storyboard.columns * storyboard.rows;
  const sheetIndex = Math.floor(frameIndex / cellsPerSheet);
  const sheet = storyboard.sheets[Math.min(sheetIndex, storyboard.sheets.length - 1)];
  if (!sheet) {
    return undefined;
  }
  const firstFrameIndexForSheet = Math.round(sheet.startTime / storyboard.intervalSeconds);
  const localFrameIndex = clamp(frameIndex - firstFrameIndexForSheet, 0, sheet.frameCount - 1);
  const cellIndex = localFrameIndex % cellsPerSheet;
  const cellCol = cellIndex % storyboard.columns;
  const cellRow = Math.floor(cellIndex / storyboard.columns);
  return {
    sheetUrl: sheet.url,
    frameWidth: storyboard.frameWidth,
    frameHeight: storyboard.frameHeight,
    sheetWidth: storyboard.frameWidth * storyboard.columns,
    sheetHeight: storyboard.frameHeight * storyboard.rows,
    offsetX: negativeOffset(cellCol * storyboard.frameWidth),
    offsetY: negativeOffset(cellRow * storyboard.frameHeight)
  };
}

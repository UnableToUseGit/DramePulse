import {
  getChapterTicks,
  getChapterTitleRailItems,
  getSnappedTimelineTime,
  getTimelineTimeFromPageX,
  getStoryboardCell,
  getStoryChapterAtTime,
  getTimelinePresentation,
  normalizeStoryChapters,
  normalizeStoryboardManifest
} from "../storyNavigation";

const chapters = [
  {
    chapterId: "ch_001",
    videoId: "demo",
    startTime: 0,
    endTime: 10,
    title: "债主堵门",
    summary: "债主上门。",
    importance: 0.6
  },
  {
    chapterId: "ch_002",
    videoId: "demo",
    startTime: 10,
    endTime: 20,
    title: "女主反击",
    summary: "女主反击。",
    importance: 0.8
  }
];

describe("storyNavigation", () => {
  it("finds the left-closed story chapter at a playback time", () => {
    expect(getStoryChapterAtTime(chapters, 0)?.title).toBe("债主堵门");
    expect(getStoryChapterAtTime(chapters, 9.99)?.title).toBe("债主堵门");
    expect(getStoryChapterAtTime(chapters, 10)?.title).toBe("女主反击");
    expect(getStoryChapterAtTime(chapters, 20)?.title).toBe("女主反击");
  });

  it("builds chapter tick percentages without the zero boundary", () => {
    expect(getChapterTicks(chapters, 20)).toEqual([{ chapterId: "ch_002", percent: 50 }]);
  });

  it("uses a thicker timeline presentation while dragging", () => {
    expect(getTimelinePresentation(false)).toEqual({
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
    });
    expect(getTimelinePresentation(true)).toEqual({
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
    });
  });

  it("maps fullscreen scrub page x to timeline time after drag activation", () => {
    expect(getTimelineTimeFromPageX({ pageX: 20, trackPageX: 20, trackWidth: 200, duration: 100 })).toBe(0);
    expect(getTimelineTimeFromPageX({ pageX: 120, trackPageX: 20, trackWidth: 200, duration: 100 })).toBe(50);
    expect(getTimelineTimeFromPageX({ pageX: 220, trackPageX: 20, trackWidth: 200, duration: 100 })).toBe(100);
    expect(getTimelineTimeFromPageX({ pageX: -200, trackPageX: 20, trackWidth: 200, duration: 100 })).toBe(0);
    expect(getTimelineTimeFromPageX({ pageX: 420, trackPageX: 20, trackWidth: 200, duration: 100 })).toBe(100);
  });

  it("snaps timeline time to nearby chapter boundaries", () => {
    expect(getSnappedTimelineTime({ time: 9.4, chapters, snapThresholdSeconds: 0.8 })).toEqual({
      time: 10,
      boundaryId: "ch_002",
      boundaryTime: 10
    });
    expect(getSnappedTimelineTime({ time: 10.6, chapters, snapThresholdSeconds: 0.8 })).toEqual({
      time: 10,
      boundaryId: "ch_002",
      boundaryTime: 10
    });
    expect(getSnappedTimelineTime({ time: 8.9, chapters, snapThresholdSeconds: 0.8 })).toEqual({
      time: 8.9
    });
  });

  it("builds a neighboring chapter title rail around the current chapter", () => {
    expect(getChapterTitleRailItems(chapters, 5)).toEqual([
      { chapterId: "ch_001", title: "债主堵门", state: "current" },
      { chapterId: "ch_002", title: "女主反击", state: "next" }
    ]);
    expect(getChapterTitleRailItems(chapters, 10)).toEqual([
      { chapterId: "ch_001", title: "债主堵门", state: "previous" },
      { chapterId: "ch_002", title: "女主反击", state: "current" }
    ]);
  });

  it("normalizes snake case story chapter payloads", () => {
    expect(
      normalizeStoryChapters([
        {
          chapter_id: "ch_001",
          video_id: "demo",
          start_time: 0,
          end_time: 10,
          title: "债主堵门",
          summary: "债主上门。",
          importance: 0.6
        },
        { chapter_id: "bad", start_time: 10, end_time: 9, title: "bad" }
      ])
    ).toEqual([chapters[0]]);
  });

  it("locates storyboard sprite sheet cell by time", () => {
    const cell = getStoryboardCell(
      {
        videoId: "demo",
        intervalSeconds: 1,
        frameWidth: 160,
        frameHeight: 90,
        columns: 5,
        rows: 5,
        sheets: [
          { url: "/sheet_000.jpg", startTime: 0, frameCount: 25 },
          { url: "/sheet_001.jpg", startTime: 25, frameCount: 10 }
        ]
      },
      27.4
    );

    expect(cell).toEqual({
      sheetUrl: "/sheet_001.jpg",
      frameWidth: 160,
      frameHeight: 90,
      sheetWidth: 800,
      sheetHeight: 450,
      offsetX: -320,
      offsetY: 0
    });
  });

  it("normalizes storyboard manifest payloads", () => {
    expect(
      normalizeStoryboardManifest({
        video_id: "demo",
        interval_seconds: 1,
        frame_width: 160,
        frame_height: 90,
        columns: 5,
        rows: 5,
        sheets: [{ url: "/sheet_000.jpg", start_time: 0, frame_count: 25 }]
      })
    ).toEqual({
      videoId: "demo",
      intervalSeconds: 1,
      frameWidth: 160,
      frameHeight: 90,
      columns: 5,
      rows: 5,
      sheets: [{ url: "/sheet_000.jpg", startTime: 0, frameCount: 25 }]
    });
  });
});

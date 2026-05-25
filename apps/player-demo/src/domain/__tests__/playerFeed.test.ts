import { getFeedPageIndex, getFeedPlaybackMode } from "../playerFeed";

describe("playerFeed", () => {
  it("rounds vertical scroll offset to the nearest feed page", () => {
    expect(getFeedPageIndex({ offsetY: 0, pageHeight: 800, itemCount: 3 })).toBe(0);
    expect(getFeedPageIndex({ offsetY: 799, pageHeight: 800, itemCount: 3 })).toBe(1);
    expect(getFeedPageIndex({ offsetY: 1601, pageHeight: 800, itemCount: 3 })).toBe(2);
  });

  it("clamps feed page index to available videos", () => {
    expect(getFeedPageIndex({ offsetY: -120, pageHeight: 800, itemCount: 3 })).toBe(0);
    expect(getFeedPageIndex({ offsetY: 2600, pageHeight: 800, itemCount: 3 })).toBe(2);
    expect(getFeedPageIndex({ offsetY: 400, pageHeight: 800, itemCount: 0 })).toBe(0);
  });

  it("shows the manual start entry only before the feed experience has started", () => {
    expect(getFeedPlaybackMode({ hasStartedFeed: false, isActive: true })).toEqual({
      shouldShowStartEntry: true,
      shouldAutoStart: false
    });
    expect(getFeedPlaybackMode({ hasStartedFeed: true, isActive: true })).toEqual({
      shouldShowStartEntry: false,
      shouldAutoStart: true
    });
    expect(getFeedPlaybackMode({ hasStartedFeed: true, isActive: false })).toEqual({
      shouldShowStartEntry: false,
      shouldAutoStart: false
    });
  });
});

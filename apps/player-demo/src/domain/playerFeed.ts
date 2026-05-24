export function getFeedPageIndex({
  offsetY,
  pageHeight,
  itemCount
}: {
  offsetY: number;
  pageHeight: number;
  itemCount: number;
}) {
  if (pageHeight <= 0 || itemCount <= 0) {
    return 0;
  }
  const rawIndex = Math.round(offsetY / pageHeight);
  return Math.min(Math.max(rawIndex, 0), itemCount - 1);
}

export function getFeedPlaybackMode({
  hasStartedFeed,
  isActive
}: {
  hasStartedFeed: boolean;
  isActive: boolean;
}) {
  return {
    shouldShowStartEntry: isActive && !hasStartedFeed,
    shouldAutoStart: isActive && hasStartedFeed
  };
}

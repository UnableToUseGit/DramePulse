export function formatResonanceCount(count: number) {
  if (count < 10000) {
    return String(count);
  }
  const wanCount = count / 10000;
  const formatted = Number.isInteger(wanCount) ? String(wanCount) : wanCount.toFixed(1);
  return `${formatted}万`;
}

export function getParticipatingCount({
  baseCount,
  hasParticipated
}: {
  baseCount: number;
  hasParticipated: boolean;
}) {
  return hasParticipated ? baseCount + 1 : baseCount;
}

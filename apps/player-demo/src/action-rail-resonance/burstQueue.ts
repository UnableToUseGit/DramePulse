export const MAX_VISIBLE_BURSTS = 12;

export function appendBurstToQueue<T>(currentBursts: T[], nextBurst: T): T[] {
  return [...currentBursts, nextBurst].slice(-MAX_VISIBLE_BURSTS);
}

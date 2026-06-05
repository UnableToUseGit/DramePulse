export type HeartbreakBurstSprite = {
  id: string;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  startScale: number;
  endScale: number;
  size: number;
  rotation: number;
  delay: number;
};

// const HEARTBREAK_BURST_SHAPE = [
//   { startX: -8, startY: 8, endX: -78, endY: -42, startScale: 0.58, endScale: 1.06, size: 24, rotation: -18, delay: 0 },
//   { startX: 6, startY: -2, endX: -36, endY: -86, startScale: 0.5, endScale: 0.9, size: 18, rotation: 12, delay: 44 },
//   { startX: 0, startY: 0, endX: 4, endY: -108, startScale: 0.56, endScale: 1.12, size: 22, rotation: -8, delay: 82 },
//   { startX: 12, startY: 6, endX: 48, endY: -78, startScale: 0.5, endScale: 0.94, size: 18, rotation: 18, delay: 126 },
//   { startX: 4, startY: 10, endX: 86, endY: -36, startScale: 0.58, endScale: 1.02, size: 24, rotation: -14, delay: 168 },
//   { startX: -16, startY: -8, endX: -58, endY: -18, startScale: 0.42, endScale: 0.78, size: 16, rotation: 22, delay: 214 },
//   { startX: 18, startY: -6, endX: 62, endY: -12, startScale: 0.44, endScale: 0.82, size: 16, rotation: -24, delay: 252 }
// ] satisfies Omit<HeartbreakBurstSprite, "id">[];

const HEARTBREAK_BURST_SHAPE = [
  { startX: -8, startY: 8, endX: -78, endY: -42, startScale: 0.58, endScale: 1.06, size: 60, rotation: -18, delay: 0 },
  { startX: 6, startY: -2, endX: -36, endY: -86, startScale: 0.5, endScale: 0.9, size: 42, rotation: 12, delay: 44 },
  { startX: 12, startY: 6, endX: 48, endY: -78, startScale: 0.5, endScale: 0.94, size: 42, rotation: 18, delay: 126 },
  { startX: 4, startY: 10, endX: 86, endY: -36, startScale: 0.58, endScale: 1.02, size: 60, rotation: -14, delay: 168 },
  { startX: 18, startY: -6, endX: 62, endY: -12, startScale: 0.44, endScale: 0.82, size: 42, rotation: -24, delay: 252 }
] satisfies Omit<HeartbreakBurstSprite, "id">[];

export function createHeartbreakBurstSprites({ burstId }: { burstId: number }): HeartbreakBurstSprite[] {
  return HEARTBREAK_BURST_SHAPE.map((sprite, index) => ({
    ...sprite,
    id: `heartbreak-burst-${burstId}-${index}`
  }));
}

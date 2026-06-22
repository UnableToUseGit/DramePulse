export type CandyBurstSprite = {
  id: string;
  startX: number;
  startY: number;
  peakX: number;
  peakY: number;
  endX: number;
  endY: number;
  size: number;
  rotation: number;
  delay: number;
};

// const CANDY_BURST_SHAPE = [
//   { startX: -10, startY: 98, peakX: -44, peakY: -136, endX: -82, endY: -46, size: 32, rotation: -112, delay: 0 },
//   { startX: -2, startY: 92, peakX: -4, peakY: -178, endX: -16, endY: -92, size: 28, rotation: -66, delay: 34 },
//   { startX: 10, startY: 104, peakX: 38, peakY: -148, endX: 66, endY: -66, size: 26, rotation: 118, delay: 72 },
//   { startX: 2, startY: 90, peakX: 62, peakY: -118, endX: 98, endY: -34, size: 32, rotation: -98, delay: 18 },
//   { startX: -12, startY: 108, peakX: -70, peakY: -102, endX: -112, endY: -20, size: 24, rotation: 142, delay: 106 }
// ] satisfies Omit<CandyBurstSprite, "id">[];

const CANDY_BURST_SHAPE = [
  { startX: -10, startY: 98, peakX: -44, peakY: -80, endX: -100, endY: -46, size: 52, rotation: -112, delay: 0 },
  { startX: -2, startY: 92, peakX: -4, peakY: -90, endX: -16, endY: -58, size: 56, rotation: -66, delay: 34 },
  { startX: 10, startY: 104, peakX: 38, peakY: -100, endX: 66, endY: -66, size: 52, rotation: 118, delay: 72 },
  { startX: 2, startY: 90, peakX: 62, peakY: -85, endX: 98, endY: -34, size: 64, rotation: -98, delay: 18 },
  { startX: -12, startY: 108, peakX: -70, peakY: -92, endX: -112, endY: -20, size: 48, rotation: 142, delay: 106 }
] satisfies Omit<CandyBurstSprite, "id">[];

export function createCandyBurstSprites({ burstId }: { burstId: number }): CandyBurstSprite[] {
  return CANDY_BURST_SHAPE.map((sprite, index) => ({
    ...sprite,
    id: `candy-burst-${burstId}-${index}`
  }));
}

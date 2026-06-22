export type LaughBurstSprite = {
  id: string;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  startScale: number;
  endScale: number;
  rotation: number;
  delay: number;
};

export type LaughBurstVariant = "full" | "combo";

const LAUGH_BURST_SHAPE = [
  { startX: -4, startY: 4, endX: -72, endY: -54, startScale: 0.54, endScale: 1.22, rotation: -12, delay: 0 },
  { startX: 6, startY: -2, endX: -34, endY: -92, startScale: 0.48, endScale: 1.05, rotation: 9, delay: 38 },
  { startX: 0, startY: 0, endX: 2, endY: -116, startScale: 0.56, endScale: 1.28, rotation: -5, delay: 74 },
  { startX: -8, startY: -4, endX: 46, endY: -86, startScale: 0.5, endScale: 1.12, rotation: 13, delay: 112 },
  { startX: 8, startY: 6, endX: 78, endY: -44, startScale: 0.52, endScale: 1.2, rotation: -10, delay: 150 },
  { startX: -2, startY: 10, endX: -42, endY: -22, startScale: 0.44, endScale: 0.94, rotation: 15, delay: 194 },
  { startX: 4, startY: 8, endX: 38, endY: -18, startScale: 0.46, endScale: 0.98, rotation: -14, delay: 232 }
] satisfies Omit<LaughBurstSprite, "id">[];

const LAUGH_COMBO_BURST_SHAPE = [
  { startX: -4, startY: 4, endX: -48, endY: -38, startScale: 0.5, endScale: 1.04, rotation: -10, delay: 0 },
  { startX: 2, startY: 0, endX: 0, endY: -72, startScale: 0.52, endScale: 1.18, rotation: 6, delay: 28 },
  { startX: 8, startY: 5, endX: 52, endY: -34, startScale: 0.48, endScale: 1.02, rotation: 12, delay: 56 }
] satisfies Omit<LaughBurstSprite, "id">[];

export function createLaughBurstSprites({
  burstId,
  variant = "full"
}: {
  burstId: number;
  variant?: LaughBurstVariant;
}): LaughBurstSprite[] {
  const shape = variant === "combo" ? LAUGH_COMBO_BURST_SHAPE : LAUGH_BURST_SHAPE;

  return shape.map((sprite, index) => ({
    ...sprite,
    id: `laugh-burst-${burstId}-${index}`
  }));
}

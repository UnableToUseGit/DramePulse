import { createHeartbreakBurstSprites } from "../heartbreakBurst";

describe("heartbreak burst sprite generation", () => {
  it("creates the same broken-heart burst shape for every tap", () => {
    const firstTap = createHeartbreakBurstSprites({ burstId: 1 });
    const laterTap = createHeartbreakBurstSprites({ burstId: 7 });

    expect(firstTap.length).toBeGreaterThanOrEqual(5);
    expect(firstTap.length).toBeLessThanOrEqual(7);
    expect(laterTap).toHaveLength(firstTap.length);
    expect(firstTap.map((sprite) => sprite.endX)).toEqual(laterTap.map((sprite) => sprite.endX));
    expect(firstTap.map((sprite) => sprite.endY)).toEqual(laterTap.map((sprite) => sprite.endY));
  });

  it("floats broken hearts upward from near center instead of raining downward", () => {
    const sprites = createHeartbreakBurstSprites({ burstId: 2 });

    expect(sprites.every((sprite) => Math.abs(sprite.startX) <= 24)).toBe(true);
    expect(sprites.every((sprite) => Math.abs(sprite.startY) <= 18)).toBe(true);
    expect(sprites.every((sprite) => sprite.endY < sprite.startY)).toBe(true);
    expect(sprites.every((sprite) => sprite.size >= 40)).toBe(true);
    expect(sprites.some((sprite) => Math.abs(sprite.endX) >= 62)).toBe(true);
  });

  it("assigns stable unique ids per burst", () => {
    const sprites = createHeartbreakBurstSprites({ burstId: 5 });
    const lastIndex = sprites.length - 1;

    expect(sprites[0]?.id).toBe("heartbreak-burst-5-0");
    expect(sprites[lastIndex]?.id).toBe(`heartbreak-burst-5-${lastIndex}`);
  });
});

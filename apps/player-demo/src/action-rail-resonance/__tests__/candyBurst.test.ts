import { createCandyBurstSprites } from "../candyBurst";

describe("candy burst sprite generation", () => {
  it("creates the same candy toss shape for every tap", () => {
    const firstTap = createCandyBurstSprites({ burstId: 1 });
    const laterTap = createCandyBurstSprites({ burstId: 8 });

    expect(firstTap).toHaveLength(5);
    expect(laterTap).toHaveLength(5);
    expect(firstTap.map((sprite) => sprite.startY)).toEqual(laterTap.map((sprite) => sprite.startY));
    expect(firstTap.map((sprite) => sprite.peakY)).toEqual(laterTap.map((sprite) => sprite.peakY));
    expect(firstTap.map((sprite) => sprite.endY)).toEqual(laterTap.map((sprite) => sprite.endY));
  });

  it("throws candies upward from a lower hand position with a natural falloff", () => {
    const sprites = createCandyBurstSprites({ burstId: 2 });

    expect(sprites.every((sprite) => sprite.startY > 60)).toBe(true);
    expect(sprites.every((sprite) => sprite.peakY < -70)).toBe(true);
    expect(sprites.every((sprite) => sprite.endY > sprite.peakY)).toBe(true);
    expect(sprites.every((sprite) => sprite.size >= 24)).toBe(true);
    expect(sprites.filter((sprite) => sprite.endY < 0)).toHaveLength(5);
  });

  it("assigns stable unique ids per burst", () => {
    const sprites = createCandyBurstSprites({ burstId: 3 });

    expect(sprites[0]?.id).toBe("candy-burst-3-0");
    expect(sprites[4]?.id).toBe("candy-burst-3-4");
  });
});

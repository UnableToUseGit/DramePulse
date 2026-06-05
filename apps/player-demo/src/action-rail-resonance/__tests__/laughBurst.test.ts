import { createLaughBurstSprites } from "../laughBurst";

describe("laugh burst sprite generation", () => {
  it("creates the same laugh wave shape for every tap", () => {
    const firstTap = createLaughBurstSprites({ burstId: 1 });
    const laterTap = createLaughBurstSprites({ burstId: 6 });

    expect(firstTap).toHaveLength(7);
    expect(laterTap).toHaveLength(7);
    expect(firstTap.map((sprite) => sprite.endX)).toEqual(laterTap.map((sprite) => sprite.endX));
    expect(firstTap.map((sprite) => sprite.endY)).toEqual(laterTap.map((sprite) => sprite.endY));
  });

  it("makes every svg laugh glyph emerge from center and grow outward", () => {
    const sprites = createLaughBurstSprites({ burstId: 2 });

    expect(sprites.every((sprite) => !("text" in sprite))).toBe(true);
    expect(sprites.every((sprite) => Math.abs(sprite.startX) <= 12)).toBe(true);
    expect(sprites.every((sprite) => Math.abs(sprite.startY) <= 12)).toBe(true);
    expect(sprites.every((sprite) => sprite.endScale > sprite.startScale)).toBe(true);
    expect(sprites.some((sprite) => sprite.endY < -40)).toBe(true);
  });

  it("uses a lighter glyph wave for follow-up combo taps", () => {
    const fullBurst = createLaughBurstSprites({ burstId: 3 });
    const comboBurst = createLaughBurstSprites({ burstId: 3, variant: "combo" });

    expect(comboBurst).toHaveLength(3);
    expect(comboBurst.length).toBeLessThan(fullBurst.length);
    expect(comboBurst.every((sprite) => sprite.endScale > sprite.startScale)).toBe(true);
    expect(comboBurst.some((sprite) => sprite.endY < -40)).toBe(true);
  });

  it("assigns stable unique ids per burst", () => {
    const sprites = createLaughBurstSprites({ burstId: 4 });

    expect(sprites[0]?.id).toBe("laugh-burst-4-0");
    expect(sprites[6]?.id).toBe("laugh-burst-4-6");
  });
});

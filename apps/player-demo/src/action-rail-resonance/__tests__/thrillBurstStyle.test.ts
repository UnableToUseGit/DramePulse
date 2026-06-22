declare const require: (path: string) => any;

describe("thrill burst style", () => {
  it("uses the same lit orange for the bang mark as the thrill glyph", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/action-rail-resonance/ActionRailResonanceBurstLayer.tsx", "utf8");

    expect(source).toContain("thrillBang");
    expect(source).toContain('color: "#ff6a1a"');
    expect(source).not.toContain('color: "#ffd166"');
  });
});

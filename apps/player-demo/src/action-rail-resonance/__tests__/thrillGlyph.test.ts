declare const require: (path: string) => any;

describe("ThrillWordGlyph", () => {
  it("renders the thrill glyph without outline strokes", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/action-rail-resonance/ThrillWordGlyph.tsx", "utf8");

    expect(source).toContain('const fill = isLit ? "#ff6a1a" : "#ffffff"');
    expect(source).not.toContain("const stroke =");
    expect(source).not.toContain("stroke={");
    expect(source).not.toContain("strokeWidth");
  });
});

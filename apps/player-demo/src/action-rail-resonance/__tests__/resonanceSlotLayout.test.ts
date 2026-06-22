declare const require: (path: string) => any;

describe("ActionRailResonanceSlot layout", () => {
  it("keeps a fixed rail slot reserved while the resonance button is hidden", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/action-rail-resonance/ActionRailResonanceSlot.tsx", "utf8");

    expect(source).toContain("const shouldShowAnimatedContent");
    expect(source).toContain("height: 58");
    expect(source).not.toContain("return null;");
  });
});

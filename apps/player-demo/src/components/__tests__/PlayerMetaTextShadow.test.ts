declare const require: (path: string) => any;

describe("player meta text shadow", () => {
  it("does not apply heavy text shadows to episode, title, or summary copy", () => {
    const fs = require("fs");
    const topBarSource = fs.readFileSync("src/components/PlayerTopBar.tsx", "utf8");
    const metaSource = fs.readFileSync("src/components/PlayerMeta.tsx", "utf8");

    expect(topBarSource).not.toContain("playerOverlay.textShadow");
    expect(metaSource).not.toContain("playerOverlay.textShadow");
  });
});

declare const require: (path: string) => any;

describe("PlayerBottomTabs", () => {
  it("uses an opaque dock color so tabs look consistent across page backgrounds", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerBottomTabs.tsx", "utf8");

    expect(source).toContain('backgroundColor: "#1C1C1E"');
    expect(source).not.toContain('backgroundColor: "rgba(10,10,10,0.9)"');
  });
});

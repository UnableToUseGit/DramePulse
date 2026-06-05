declare const require: (path: string) => any;

describe("PlayerChrome meta presentation", () => {
  it("uses a cleaner series-player meta layout without tags or summary cards", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerChrome.tsx", "utf8");

    expect(source).toContain('showTags={mode !== "series"}');
    expect(source).toContain('summaryPresentation={mode === "series" ? "inline" : "card"}');
  });
});

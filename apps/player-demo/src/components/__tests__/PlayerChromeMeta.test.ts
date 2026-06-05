declare const require: (path: string) => any;

describe("PlayerChrome meta presentation", () => {
  it("keeps home tags while using inline summaries across player modes", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerChrome.tsx", "utf8");

    expect(source).toContain('showTags={mode !== "series"}');
    expect(source).toContain('summaryPresentation="inline"');
  });
});

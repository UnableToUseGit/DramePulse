declare const require: (path: string) => any;

describe("DanmakuEntryArea", () => {
  it("keeps the fixed danmaku button out of inner voice prompt layout changes", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/DanmakuEntryArea.tsx", "utf8");

    expect(source).toContain("innerVoiceSlot");
    expect(source).toContain("position: \"absolute\"");
    expect(source).toContain("left: 42");
    expect(source).toContain("width: 34");
    expect(source).toContain("width: 220");
    expect(source).toContain("alignItems: \"flex-start\"");
    expect(source).not.toContain("gap: spacing.sm");
  });

  it("renders API inner voice cues before falling back to the interaction lab example", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/DanmakuEntryArea.tsx", "utf8");

    expect(source.indexOf("innerVoiceCue ?")).toBeGreaterThan(-1);
    expect(source.indexOf("!innerVoiceCue && showInnerVoice && showInnerVoiceExample")).toBeGreaterThan(
      source.indexOf("innerVoiceCue ?")
    );
    expect(source).toContain("onInnerVoiceExitComplete");
  });
});

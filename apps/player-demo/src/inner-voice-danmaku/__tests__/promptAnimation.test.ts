declare const require: (path: string) => any;

describe("InnerVoicePrompt animation", () => {
  it("enters as a soft slide from the danmaku entry instead of popping in place", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/inner-voice-danmaku/InnerVoicePrompt.tsx", "utf8");

    expect(source).toContain("ENTRY_OFFSET_X");
    expect(source).toContain("ENTRY_OFFSET_Y");
    expect(source).toContain("entryTranslateX");
    expect(source).toContain("entryTranslateY");
    expect(source).toContain("withTiming(0,");
  });

  it("keeps the prompt bubble content-sized within its max width", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/inner-voice-danmaku/InnerVoicePrompt.tsx", "utf8");

    expect(source).toContain("alignSelf: \"flex-start\"");
    expect(source).toContain("maxWidth: 220");
    expect(source).not.toContain("width: 220");
  });
});

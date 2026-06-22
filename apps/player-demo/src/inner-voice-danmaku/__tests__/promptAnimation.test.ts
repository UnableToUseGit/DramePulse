declare const require: (path: string) => any;

describe("InnerVoicePrompt animation", () => {
  it("enters as a bubble breathed out from the danmaku entry instead of popping in place", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/inner-voice-danmaku/InnerVoicePrompt.tsx", "utf8");

    expect(source).toContain("ENTRY_OFFSET_X");
    expect(source).toContain("ENTRY_OFFSET_Y");
    expect(source).toContain("entryTranslateX");
    expect(source).toContain("entryTranslateY");
    expect(source).toContain("BUBBLE_ENTRY_SCALE");
    expect(source).toContain("bubbleScale");
    expect(source).toContain("contentReveal");
    expect(source).toContain("BUBBLE_BREATH_MS");
    expect(source).toContain("CONTENT_REVEAL_DELAY_MS");
    expect(source).toContain("withSequence");
    expect(source).toContain("withDelay(CONTENT_REVEAL_DELAY_MS");
    expect(source).toContain("withTiming(0,");
  });

  it("keeps the prompt bubble content-sized within its max width", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/inner-voice-danmaku/InnerVoicePrompt.tsx", "utf8");

    expect(source).toContain("alignSelf: \"flex-start\"");
    expect(source).toContain("maxWidth: 220");
    expect(source).not.toContain("width: 220");
  });

  it("uses the same translucent black background as the danmaku entry button", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/inner-voice-danmaku/InnerVoicePrompt.tsx", "utf8");

    expect(source).toContain("backgroundColor: \"rgba(0,0,0,0.46)\"");
    expect(source).not.toContain("backgroundColor: \"rgba(8,8,10,0.76)\"");
  });
});

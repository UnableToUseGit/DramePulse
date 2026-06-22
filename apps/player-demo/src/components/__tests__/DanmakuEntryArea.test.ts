declare const require: (path: string) => any;

describe("DanmakuEntryArea", () => {
  it("keeps the fixed danmaku button and inner voice slot decoupled from watch assistant", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/DanmakuEntryArea.tsx", "utf8");
    const danmakuButtonSource = fs.readFileSync("src/components/DanmakuEntryButton.tsx", "utf8");

    expect(source).not.toContain("assistantButton");
    expect(source).not.toContain("onOpenWatchAssistant");
    expect(source).not.toContain("AI陪看");
    expect(source).not.toContain("观看助手");
    expect(source).toContain("<DanmakuEntryButton />");
    expect(source).toContain("innerVoiceSlot");
    expect(source).toContain("position: \"absolute\"");
    expect(source).toContain("left: 42");
    expect(source).toContain("height: 34");
    expect(source).toContain("top: -1");
    expect(danmakuButtonSource).toContain("width: 34");
    expect(danmakuButtonSource).toContain("height: 34");
    expect(danmakuButtonSource).toContain('backgroundColor: "rgba(0,0,0,0.46)"');
    expect(danmakuButtonSource).toContain('borderColor: "rgba(255,255,255,0.13)"');
    expect(source).toContain("width: 220");
    expect(source).toContain("alignItems: \"flex-start\"");
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

describe("PlayerConversationEntryArea", () => {
  it("places the watch assistant entry beside the danmaku entry without coupling it into DanmakuEntryArea", () => {
    const fs = require("fs");
    const chromeSource = fs.readFileSync("src/components/PlayerChrome.tsx", "utf8");
    const metaSource = fs.readFileSync("src/components/PlayerMeta.tsx", "utf8");
    const conversationSource = fs.readFileSync("src/components/PlayerConversationEntryArea.tsx", "utf8");
    const entrySource = fs.readFileSync("src/components/WatchAssistantEntry.tsx", "utf8");

    expect(chromeSource).not.toContain("assistantSlot");
    expect(chromeSource).not.toContain("WatchAssistantEntry");
    expect(metaSource).toContain("PlayerConversationEntryArea");
    expect(metaSource).toContain("onOpenWatchAssistant={onOpenWatchAssistant}");
    expect(conversationSource).toContain("<WatchAssistantEntry");
    expect(conversationSource).toContain("<DanmakuEntryArea");
    expect(conversationSource.indexOf("<WatchAssistantEntry")).toBeLessThan(
      conversationSource.indexOf("<DanmakuEntryArea")
    );
    expect(conversationSource).toContain("flexDirection: \"row\"");
    expect(conversationSource).toContain("gap: 8");
    expect(conversationSource).toContain("height: 34");
    expect(entrySource).toContain('name="sparkles"');
    expect(entrySource).not.toContain("<Text");
    expect(entrySource).not.toContain("chevron-forward");
    expect(entrySource).toContain("width: 34");
    expect(entrySource).toContain("height: 34");
    expect(entrySource).toContain('backgroundColor: "rgba(0,0,0,0.46)"');
    expect(entrySource).toContain('borderColor: "rgba(255,255,255,0.13)"');
  });
});

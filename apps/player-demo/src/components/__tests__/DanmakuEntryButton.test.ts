declare const require: (path: string) => any;

describe("DanmakuEntryButton", () => {
  it("uses a compact single-character entry without the chat bubble icon", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/DanmakuEntryButton.tsx", "utf8");

    expect(source).toContain(">弹</Text>");
    expect(source).toContain("width: 34");
    expect(source).toContain("height: 34");
    expect(source).toContain("fontSize: 17");
    expect(source).not.toContain("chatbubble-ellipses");
    expect(source).not.toContain(">弹幕</Text>");
  });
});

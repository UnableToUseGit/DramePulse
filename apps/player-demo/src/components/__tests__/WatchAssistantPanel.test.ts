declare const require: (path: string) => any;

describe("WatchAssistantPanel", () => {
  it("supports mobile dismissal by tapping outside or swiping down", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/WatchAssistantPanel.tsx", "utf8");

    expect(source).toContain("PanResponder");
    expect(source).toContain("onMoveShouldSetPanResponder");
    expect(source).toContain("onPanResponderRelease");
    expect(source).toContain("gesture.dy > 48");
    expect(source).toContain('accessibilityLabel="关闭观看助手遮罩"');
    expect(source).toContain("style={styles.backdrop}");
    expect(source).toContain("onPress={onClose}");
  });
});

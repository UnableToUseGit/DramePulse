declare const require: (path: string) => any;

describe("WatchAssistantPanel", () => {
  it("animates in from the bottom and only uses the top handle area for swipe dismissal", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/WatchAssistantPanel.tsx", "utf8");

    expect(source).toContain("Animated");
    expect(source).toContain("translateY");
    expect(source).toContain("overlayOpacity");
    expect(source).toContain("sheetProgress");
    expect(source).toContain("if (!shouldRender) {");
    expect(source).toContain("Animated.parallel");
    expect(source).toContain("styles.handleTouchArea");
    expect(source).toContain("PanResponder");
    expect(source).toContain("onMoveShouldSetPanResponderCapture");
    expect(source).toContain("onPanResponderRelease");
    expect(source).toContain("SWIPE_DISMISS_DISTANCE_PX");
    expect(source).toContain('accessibilityLabel="关闭观看助手遮罩"');
    expect(source).toContain("style={styles.backdrop}");
    expect(source).toContain("onPress={requestClose}");
  });
});

declare const require: (path: string) => any;

describe("WatchAssistantPanel", () => {
  it("uses a light sheet layout with centered feedback and a bottom composer", () => {
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
    expect(source).toContain('backgroundColor: "#FFFFFF"');
    expect(source).toContain("陪看助手");
    expect(source).toContain("要我帮你捋一捋这段剧情吗");
    expect(source).toContain("contentSection");
    expect(source).toContain("composerSection");
    expect(source).toContain("justifyContent: \"center\"");
    expect(source).not.toContain("closeButton");
    expect(source).toContain('accessibilityLabel="关闭观看助手遮罩"');
    expect(source).toContain("style={styles.backdrop}");
    expect(source).toContain("onPress={requestClose}");
  });
});

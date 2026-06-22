declare const require: (path: string) => any;

describe("RoleCommerceProductSheet", () => {
  it("uses the same light bottom-sheet visual language as the watch assistant", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/RoleCommerceProductSheet.tsx", "utf8");

    expect(source).toContain('backgroundColor: "rgba(0,0,0,0.18)"');
    expect(source).toContain('backgroundColor: "#FFFFFF"');
    expect(source).toContain("borderTopLeftRadius: radii.panel");
    expect(source).toContain("borderTopRightRadius: radii.panel");
    expect(source).toContain('borderColor: "rgba(255,255,255,0.72)"');
    expect(source).toContain('color: "#3A3A3A"');
    expect(source).toContain('backgroundColor: "#F3F4F6"');
    expect(source).not.toContain('backgroundColor: "rgba(12,12,14,0.97)"');
  });

  it("animates the scrim separately from the sheet and omits the top-right close button", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/RoleCommerceProductSheet.tsx", "utf8");

    expect(source).toContain("Animated");
    expect(source).toContain("backdropOpacity");
    expect(source).toContain("sheetTranslateY");
    expect(source).toContain('animationType="none"');
    expect(source).not.toContain('animationType="slide"');
    expect(source).not.toContain('name="close"');
  });

  it("supports dragging the handle downward to dismiss the sheet", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/RoleCommerceProductSheet.tsx", "utf8");

    expect(source).toContain("PanResponder");
    expect(source).toContain("SWIPE_DISMISS_DISTANCE_PX");
    expect(source).toContain("SWIPE_DISMISS_VELOCITY");
    expect(source).toContain("sheetTranslateY.setValue(Math.max(0, gesture.dy))");
    expect(source).toContain("onStartShouldSetPanResponder");
    expect(source).toContain("onMoveShouldSetPanResponder");
    expect(source).toContain("onPanResponderRelease");
    expect(source).toContain("closeWithSheetAnimation");
    expect(source).toContain("styles.handleTouchArea");
    expect(source).toContain("<View style={styles.handleTouchArea} {...panResponder.panHandlers}>");
    expect(source).not.toContain("Animated.add");
  });
});

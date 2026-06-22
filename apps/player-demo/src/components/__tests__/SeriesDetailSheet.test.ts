declare const require: (path: string) => any;

describe("SeriesDetailSheet", () => {
  it("renders as a clean white sheet without scrim, tags, favorite CTA, or oversized heavy text", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/SeriesDetailSheet.tsx", "utf8");

    expect(source).toContain("backgroundColor: \"transparent\"");
    expect(source).not.toContain("rgba(0,0,0,0.18)");
    expect(source).not.toContain("favoriteButton");
    expect(source).not.toContain("favoriteText");
    expect(source).not.toContain('name="close"');
    expect(source).not.toContain("styles.tags");
    expect(source).not.toContain("styles.tag");
    expect(source).not.toContain("fontWeight: \"900\"");
    expect(source).not.toContain("fontSize: 26");
    expect(source).not.toContain("fontSize: 24");
    expect(source).not.toContain("fontSize: 22");
  });

  it("supports drag-down dismissal from the sheet top edge", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/SeriesDetailSheet.tsx", "utf8");

    expect(source).toContain("PanResponder.create");
    expect(source).toContain("DRAG_DISMISS_DISTANCE_PX");
    expect(source).toContain("topDragArea");
    expect(source).toContain("closeWithSheetAnimation");
    expect(source).toContain('animationType="none"');
    expect(source).not.toContain("dragY.setValue(0);\n            onClose();");
  });

  it("keeps the sheet offscreen before the opening animation starts", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/SeriesDetailSheet.tsx", "utf8");

    expect(source).toContain("useRef(new Animated.Value(offscreenY)).current");
    expect(source).toContain("dragY.setValue(offscreenY)");
    expect(source).not.toContain("useRef(new Animated.Value(0)).current");
    expect(source).not.toContain("dragY.setValue(0);");
  });
});

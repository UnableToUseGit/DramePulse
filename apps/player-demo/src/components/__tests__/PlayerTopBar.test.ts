jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons"
}));

import { formatEpisodeDisplayLabel } from "../PlayerTopBar";

describe("formatEpisodeDisplayLabel", () => {
  it("formats ep-style episode labels as Chinese episode titles", () => {
    expect(formatEpisodeDisplayLabel("ep07")).toBe("第7集");
    expect(formatEpisodeDisplayLabel("ep7")).toBe("第7集");
    expect(formatEpisodeDisplayLabel("第2集")).toBe("第2集");
    expect(formatEpisodeDisplayLabel("广告")).toBe("广告");
    expect(formatEpisodeDisplayLabel(undefined)).toBe("返回");
  });

  it("renders the home menu icon without the soft circular panel", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerTopBar.tsx", "utf8");

    expect(source).toContain("<View style={styles.menuButton}>");
    expect(source).not.toContain("...playerOverlay.softPanel");
  });
});

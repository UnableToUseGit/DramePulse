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
});

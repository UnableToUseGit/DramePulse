jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons"
}));

import { SERIES_EPISODE_BAR_STYLE_SPEC } from "../SeriesEpisodeBar";

describe("SERIES_EPISODE_BAR_STYLE_SPEC", () => {
  it("keeps the episode picker compact, centered, and visually separate from the black dock", () => {
    expect(SERIES_EPISODE_BAR_STYLE_SPEC.height).toBeLessThan(54);
    expect(SERIES_EPISODE_BAR_STYLE_SPEC.left).toBe(SERIES_EPISODE_BAR_STYLE_SPEC.right);
    expect(SERIES_EPISODE_BAR_STYLE_SPEC.backgroundColor).toBe("rgba(36, 36, 40, 0.94)");
  });
});

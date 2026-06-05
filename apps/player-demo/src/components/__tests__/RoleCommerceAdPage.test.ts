declare const require: (path: string) => any;

describe("RoleCommerceAdPage", () => {
  it("wires the series back action into the ad page top bar", () => {
    const fs = require("fs");
    const adPageSource = fs.readFileSync("src/components/RoleCommerceAdPage.tsx", "utf8");
    const feedSource = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");

    expect(feedSource).toContain("onBack={onBack}");
    expect(adPageSource).toContain("onBack?: () => void");
    expect(adPageSource).toContain("onBack={onBack}");
  });

  it("uses the same series episode dock on ad pages as normal series player pages", () => {
    const fs = require("fs");
    const adPageSource = fs.readFileSync("src/components/RoleCommerceAdPage.tsx", "utf8");
    const feedSource = fs.readFileSync("src/components/PlayerFeed.tsx", "utf8");

    expect(feedSource).toContain("seriesEpisodeCount={seriesEpisodeCount}");
    expect(feedSource).toContain("onOpenSeriesDetail={onOpenSeriesDetail}");
    expect(adPageSource).toContain("SeriesEpisodeBar");
    expect(adPageSource).toContain("seriesEpisodeCount?: number");
    expect(adPageSource).toContain("onOpenSeriesDetail?: () => void");
  });
});

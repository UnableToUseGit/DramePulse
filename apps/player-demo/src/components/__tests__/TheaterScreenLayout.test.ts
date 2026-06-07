declare const require: (path: string) => any;

describe("TheaterScreen layout", () => {
  it("docks the bottom tabs below the theater list instead of overlaying covers", () => {
    const fs = require("fs");
    const theaterSource = fs.readFileSync("src/screens/TheaterScreen.tsx", "utf8");
    const tabsSource = fs.readFileSync("src/components/PlayerBottomTabs.tsx", "utf8");

    expect(theaterSource).toContain('presentation="docked"');
    expect(theaterSource).not.toContain("paddingBottom: 104");
    expect(tabsSource).toContain('presentation = "overlay"');
    expect(tabsSource).toContain("presentation === \"overlay\" ? styles.overlayRoot : styles.dockedRoot");
  });

  it("docks home player tabs in normal layout instead of the absolute player chrome overlay", () => {
    const fs = require("fs");
    const pageSource = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const chromeSource = fs.readFileSync("src/components/PlayerChrome.tsx", "utf8");

    expect(pageSource).toContain('presentation="docked"');
    expect(pageSource).toContain('mode === "home" ? (');
    expect(pageSource).not.toContain('videoViewport: {\n    position: "absolute"');
    expect(chromeSource).not.toContain("PlayerBottomTabs");
  });

  it("fills the series player bottom dock with the same opaque tab color", () => {
    const fs = require("fs");
    const pageSource = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");

    expect(pageSource).toContain('mode === "series" ? (');
    expect(pageSource).toContain("styles.seriesBottomDock");
    expect(pageSource).toContain('backgroundColor: "#1C1C1E"');
  });

  it("uses cloud series cover URLs before local cover fallbacks", () => {
    const fs = require("fs");
    const theaterSource = fs.readFileSync("src/screens/TheaterScreen.tsx", "utf8");
    const detailSheetSource = fs.readFileSync("src/components/SeriesDetailSheet.tsx", "utf8");

    expect(theaterSource).toContain("getSeriesCoverSource(series.coverVideo.seriesId)");
    expect(theaterSource).toContain("series.coverUrl && !didFailCloudCover ? { uri: series.coverUrl }");
    expect(theaterSource).toContain("onError={() => setDidFailCloudCover(true)}");
    expect(theaterSource).not.toContain("{ uri: item.coverVideo.streamUrl }");
    expect(detailSheetSource).toContain("getSeriesCoverSource(series.coverVideo.seriesId)");
    expect(detailSheetSource).toContain("series.coverUrl && !didFailCloudCover ? { uri: series.coverUrl }");
    expect(detailSheetSource).toContain("onError={() => setDidFailCloudCover(true)}");
    expect(detailSheetSource).not.toContain("{ uri: series.coverVideo.streamUrl }");
  });
});

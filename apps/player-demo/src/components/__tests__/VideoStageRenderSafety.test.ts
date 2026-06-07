declare const require: (path: string) => any;

describe("VideoStage render safety", () => {
  it("does not record resume initialization from the useVideoPlayer setup callback", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/VideoStage.tsx", "utf8");
    const setupStart = source.indexOf("useVideoPlayer(streamUrl");
    const setupEnd = source.indexOf(");", setupStart);
    const setupSource = source.slice(setupStart, setupEnd);

    expect(setupSource).not.toContain('recordObservation("resume_position_initialized"');
  });

  it("keeps feed video stage mounted from a single PlayerPage render site", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");
    const renderSiteCount = (source.match(/<VideoStage/g) ?? []).length;

    expect(renderSiteCount).toBe(1);
    expect(source).not.toContain(":preload");
  });

  it("disables iOS Live Text frame analysis controls over the custom player chrome", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/VideoStage.tsx", "utf8");

    expect(source).toContain("allowsVideoFrameAnalysis={false}");
  });

  it("loads playback assets in PlayerPage and renders controls from the enhanced video", () => {
    const fs = require("fs");
    const source = fs.readFileSync("src/components/PlayerPage.tsx", "utf8");

    expect(source).toContain("loadPlaybackAssets");
    expect(source).toContain("playbackAssetVideo");
    expect(source).toContain("setPlaybackAssetVideo(assets.video)");
    expect(source).toContain("const displayVideo = playbackAssetVideo?.videoId === video.videoId ? playbackAssetVideo : video");
    expect(source).toContain("storyboard={displayVideo.storyboard}");
  });
});
